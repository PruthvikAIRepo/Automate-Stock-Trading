"""
Market AI Intelligence — real AI analysis of live market data.

Uses OpenAI gpt-4.1-mini to generate investor-friendly market insights
from live index data. Cached for 5 minutes to control costs.

Cost: ~$0.0005 per call (~$0.14/day at 5-min intervals).
"""

import json
import logging
import os
import time
from datetime import datetime

log = logging.getLogger(__name__)

# Cache: store last AI analysis to avoid calling on every page load
_cache = {"analysis": None, "timestamp": 0, "data_hash": ""}
CACHE_TTL = 300  # 5 minutes


def _build_market_snapshot(idx_data, breadth, fii_dii):
    """
    Build a structured market data snapshot for the AI prompt.
    Only includes what matters for investor-grade analysis.
    """
    hero = idx_data.get("hero", [])
    nifty = hero[0] if len(hero) > 0 else {}
    banknifty = hero[1] if len(hero) > 1 else {}
    vix = idx_data.get("vix", {}) or {}

    # Top gainers and losers from sector performance
    sectors = idx_data.get("sector_performance", [])
    top_gainers = [s for s in sectors if s["change_pct"] > 0]
    top_losers = [s for s in sectors if s["change_pct"] < 0]

    # Broad market indices for context
    all_table = idx_data.get("all_table", [])
    broad_indices = [i for i in all_table if i.get("category") == "broad_market"][:8]

    snapshot = {
        "date": datetime.now().strftime("%A, %d %B %Y"),
        "time": datetime.now().strftime("%I:%M %p IST"),
        "nifty50": {
            "value": nifty.get("value", 0),
            "change": nifty.get("change", 0),
            "change_pct": nifty.get("change_pct", 0),
            "open": nifty.get("open", 0),
            "high": nifty.get("high", 0),
            "low": nifty.get("low", 0),
        },
        "banknifty": {
            "value": banknifty.get("value", 0),
            "change": banknifty.get("change", 0),
            "change_pct": banknifty.get("change_pct", 0),
        },
        "vix": vix.get("value", 0),
        "vix_change_pct": vix.get("change_pct", 0),
        "breadth": {
            "advances": breadth.get("advances", 0),
            "declines": breadth.get("declines", 0),
            "advance_pct": breadth.get("adv_pct", 50),
        },
        "fii_net_cr": fii_dii.get("fii_net", 0),
        "dii_net_cr": fii_dii.get("dii_net", 0),
        "sector_performance": [
            {"name": s["name"], "value": s["value"], "change_pct": s["change_pct"]}
            for s in sectors
        ],
        "broad_indices": [
            {"name": i["name"], "value": i["value"], "change_pct": i["change_pct"]}
            for i in broad_indices
        ],
    }
    return snapshot


def _build_prompt(snapshot):
    """
    Build the AI prompt. This is the most critical part —
    it determines the quality and usefulness of the analysis.
    """
    data_str = json.dumps(snapshot, indent=2)

    return f"""You are the AI brain of StockPulse, an Indian stock market platform for retail investors.
You are analyzing LIVE market data right now. Think like a senior market analyst explaining to a friend who invests via SIPs and mutual funds.

LIVE MARKET DATA:
{data_str}

Generate a JSON response with exactly these 4 sections. Each section must be insightful, specific, and actionable — not generic filler.

RULES:
- Use plain English. No jargon like "consolidation", "technical breakout", "resistance levels".
- Reference SPECIFIC numbers from the data (e.g., "IT is up 2.6% today" not "IT is performing well").
- Explain WHY sectors might be moving using your market knowledge (e.g., IT rises when rupee weakens, banks fall on rate hike fears).
- The "action" section must give different advice for SIP investors vs lumpsum investors.
- Be honest — if you're uncertain about a reason, say "likely because" not state it as fact.
- Keep each section concise: 2-3 sentences max.
- VIX interpretation: below 13 = very calm, 13-18 = normal, 18-24 = elevated fear, above 24 = high panic.

Return ONLY valid JSON:
{{
  "market_pulse": "What's happening in the market right now and why. Reference Nifty, Bank Nifty, and the most notable sector moves.",
  "sector_spotlight": "Analyze the biggest sector winners and losers. Explain likely reasons WHY they're moving. Connect sectors to real-world events if possible.",
  "risk_check": "Assess overall risk level based on VIX, breadth, and FII/DII flows. Tell the investor whether to worry or stay calm.",
  "investor_action": "Specific advice for SIP investors and lumpsum investors. What should they do today? Be specific and honest."
}}"""


def _data_hash(snapshot):
    """Simple hash to detect if market data changed meaningfully."""
    n = snapshot.get("nifty50", {})
    return f"{n.get('value', 0):.0f}_{n.get('change_pct', 0):.1f}"


def generate_market_analysis(idx_data, breadth, fii_dii):
    """
    Generate AI market analysis from live data.

    Returns dict with keys: market_pulse, sector_spotlight, risk_check, investor_action
    Returns None if AI unavailable or API key not set.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        log.info("No OpenAI API key — skipping AI market analysis")
        return None

    # Build snapshot
    snapshot = _build_market_snapshot(idx_data, breadth, fii_dii)
    current_hash = _data_hash(snapshot)

    # Check cache — return cached if fresh and data hasn't changed much
    now = time.time()
    if (_cache["analysis"]
            and now - _cache["timestamp"] < CACHE_TTL
            and _cache["data_hash"] == current_hash):
        log.debug("Returning cached AI analysis (age: %ds)", int(now - _cache["timestamp"]))
        return _cache["analysis"]

    # Call OpenAI
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = _build_prompt(snapshot)

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        analysis = json.loads(raw)

        # Validate expected keys
        expected = {"market_pulse", "sector_spotlight", "risk_check", "investor_action"}
        if not expected.issubset(analysis.keys()):
            log.warning("AI response missing keys: %s", expected - analysis.keys())
            return None

        # Track usage
        usage = response.usage
        log.info(
            "AI market analysis generated | tokens: %d in + %d out | model: %s",
            usage.prompt_tokens, usage.completion_tokens, response.model,
        )

        # Cache it
        _cache["analysis"] = analysis
        _cache["timestamp"] = now
        _cache["data_hash"] = current_hash

        return analysis

    except json.JSONDecodeError as e:
        log.error("AI returned invalid JSON: %s", e)
        return _cache.get("analysis")  # Return stale cache if available
    except Exception as e:
        log.error("AI market analysis failed: %s", e)
        return _cache.get("analysis")
