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


def _build_market_snapshot(idx_data, breadth, fii_dii, valuation=None):
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

    # Add valuation if available (from NSE — real PE/PB/DY)
    if valuation:
        snapshot["nifty_valuation"] = {
            "pe_ratio": valuation.get("pe", 0),
            "pb_ratio": valuation.get("pb", 0),
            "dividend_yield_pct": valuation.get("dy", 0),
        }

    # Sector rotation detection — compare 1D vs 1W relative strength
    rotation_signals = _detect_sector_rotation(sectors)
    if rotation_signals:
        snapshot["sector_rotation"] = rotation_signals

    return snapshot


def _detect_sector_rotation(sectors):
    """
    Detect sector rotation by comparing short-term (1D) vs medium-term (1W) performance.
    A rotation signal occurs when:
      - Sector strong today but weak over the week → fresh money rotating IN
      - Sector weak today but strong over the week → money rotating OUT
    """
    try:
        from app.services.indices_service import fetch_sector_timeframe_returns

        if not sectors:
            return None

        # Get 1W returns (cached, won't re-fetch if already computed)
        tf_returns = fetch_sector_timeframe_returns(sectors)
        if not tf_returns:
            return None

        signals = []
        for sec in sectors:
            token = sec.get("token", "")
            day_chg = sec.get("change_pct", 0)
            week_data = tf_returns.get(token, {})
            week_chg = week_data.get("1W")

            if week_chg is None:
                continue

            # Rotation IN: strong today (>0.5%) but weak this week (<-1.5%)
            if day_chg > 0.5 and week_chg < -1.5:
                signals.append({
                    "sector": sec["name"],
                    "type": "rotating_in",
                    "day": day_chg,
                    "week": week_chg,
                    "desc": f"{sec['name']} up {day_chg}% today but down {week_chg}% this week — fresh buying after recent weakness"
                })
            # Rotation OUT: weak today (<-0.5%) but strong this week (>1.5%)
            elif day_chg < -0.5 and week_chg > 1.5:
                signals.append({
                    "sector": sec["name"],
                    "type": "rotating_out",
                    "day": day_chg,
                    "week": week_chg,
                    "desc": f"{sec['name']} down {day_chg}% today despite being up {week_chg}% this week — profit booking / rotation out"
                })

        return signals if signals else None

    except Exception:
        return None


def _build_prompt(snapshot):
    """
    Build the AI prompt. This is the most critical part —
    it determines the quality and usefulness of the analysis.
    """
    data_str = json.dumps(snapshot, indent=2)

    return f"""You are the AI brain of StockPulse, an Indian stock market platform for retail investors.
You are analyzing LIVE market data right now. Think like a SEBI-registered investment advisor explaining to a friend who invests in mutual funds, SIPs, and sometimes trades F&O.

LIVE MARKET DATA:
{data_str}

Generate a JSON response with exactly these 6 sections. Each must be SPECIFIC — reference real numbers from the data, not generic filler.

ANALYTICAL RULES:
- Use plain English a beginner can understand. No jargon like "consolidation", "technical breakout", "resistance".
- Reference SPECIFIC numbers (e.g., "IT is up 2.6%" not "IT is doing well").
- Explain WHY sectors move using market knowledge (IT rises on weak rupee, banks fall on rate hike fears, pharma rises on FDA approvals).
- Be honest — use "likely because" when uncertain, not statements of fact.
- Keep each section 2-3 sentences. Concise and punchy.

BREADTH DIVERGENCE (critical signal):
- Nifty up but advance% < 45% → narrow rally, only a few large-caps driving, warn about weakness underneath
- Nifty down but advance% > 55% → hidden strength in midcaps/smallcaps, index fall is misleading
- Always mention this if detected — it's the #1 signal most platforms miss

VIX INTERPRETATION:
- Below 13: very calm, good for buying
- 13-18: normal conditions
- 18-24: elevated fear, be cautious
- Above 24: panic, experienced investors buy fear, beginners should wait

FII/DII FLOW SIGNALS:
- FII selling + DII buying = domestic confidence despite foreign outflow (often a bottom signal)
- FII buying + DII selling = rally may not sustain
- Both buying = strong bullish
- Both selling = serious caution

VALUATION (if PE data available):
- PE < 18: cheap, historically gives 15%+ returns over next 12 months
- PE 18-22: fair value
- PE 22-25: getting expensive
- PE > 25: expensive, caution

SECTOR ROTATION (if sector_rotation data is present):
- "rotating_in" means fresh money is entering a beaten-down sector — bullish signal for swing traders
- "rotating_out" means profit booking from a recently strong sector — caution for holders
- Mention rotation signals in sector_spotlight if detected

Return ONLY valid JSON:
{{
  "market_pulse": "What's happening right now. Reference Nifty value/change, Bank Nifty, and the most notable sector moves. If breadth diverges from index direction, call it out explicitly.",
  "sector_spotlight": "Analyze the 2-3 biggest sector winners and losers. Explain likely reasons WHY they're moving. If sector_rotation signals are present, highlight them — this is a key signal for swing traders.",
  "risk_check": "Rate risk as Low/Medium/High with reasoning. Use VIX level, breadth quality, FII/DII flows, and PE valuation. Be specific — e.g., 'Risk is HIGH — VIX at 25.5 (panic zone) combined with FII selling of Rs 9,931 Cr'.",
  "investor_action": "Specific advice for: (1) SIP investors — increase/decrease/continue and why (2) Lumpsum — deploy now or wait, and for what signal (3) F&O traders — which sectors to watch and direction. Be direct.",
  "breadth_signal": "One-line breadth interpretation. E.g., 'Only 47% stocks advancing despite Nifty being green — narrow rally driven by IT heavyweights, not broad strength.' If breadth aligns with index, say 'Broad participation confirms the move.'",
  "vix_signal": "One-line VIX interpretation with emoji. E.g., 'VIX at 25.5 signals high fear — options premiums are expensive, avoid selling naked options.'"
}}"""


def _data_hash(snapshot):
    """Simple hash to detect if market data changed meaningfully."""
    n = snapshot.get("nifty50", {})
    return f"{n.get('value', 0):.0f}_{n.get('change_pct', 0):.1f}"


def generate_market_analysis(idx_data, breadth, fii_dii, valuation=None):
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
    snapshot = _build_market_snapshot(idx_data, breadth, fii_dii, valuation)
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

        # Validate expected keys (core 4 required, 2 bonus optional)
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


# ─── PER-INDEX AI NARRATIVE ──────────────────────────────────────────────────

_idx_cache = {}  # {token: {"text": str, "ts": float}}
_IDX_CACHE_TTL = 600  # 10 minutes


def generate_index_narrative(index_info, constituents):
    """
    Generate AI narrative for a specific index detail page.
    Explains what moved the index and why, using constituent data.

    Returns: str (narrative text) or None
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    token = index_info.get("token", "")
    now = time.time()

    # Check cache
    if token in _idx_cache and (now - _idx_cache[token]["ts"]) < _IDX_CACHE_TTL:
        return _idx_cache[token]["text"]

    if not constituents:
        return None

    # Build compact snapshot
    top_up = [
        f"{s['symbol']} +{s['change_pct']}% ({'+' if s.get('pts_contribution',0)>=0 else ''}{s.get('pts_contribution',0)} pts)"
        for s in constituents.get("top_contributors", [])[:5]
    ]
    top_down = [
        f"{s['symbol']} {s['change_pct']}% ({s.get('pts_contribution',0)} pts)"
        for s in constituents.get("top_detractors", [])[:5]
    ]

    # Sector summary
    sector_summary = []
    for sec, info in list(constituents.get("sector_breakdown", {}).items())[:6]:
        sector_summary.append(f"{sec}: {info['count']} stocks, avg {info['avg_change']}%")

    prompt = f"""You are the AI analyst for StockPulse. Explain what moved {index_info.get('name', 'this index')} today in 2-3 sentences.

INDEX: {index_info.get('name')} at {index_info.get('value', 0):,.2f}, change: {index_info.get('change', 0):+,.2f} pts ({index_info.get('change_pct', 0):+.2f}%)
OHLC: Open {index_info.get('open', 0):,.0f}, High {index_info.get('high', 0):,.0f}, Low {index_info.get('low', 0):,.0f}

TOP CONTRIBUTORS (pushed index UP): {', '.join(top_up) if top_up else 'None'}
TOP DETRACTORS (dragged index DOWN): {', '.join(top_down) if top_down else 'None'}
SECTORS: {'; '.join(sector_summary)}

RULES:
- Plain English, no jargon. A beginner should understand.
- Name specific stocks and WHY they moved (use your knowledge of current events, earnings, etc.)
- Keep it to 2-3 sentences max. Punchy and insightful.
- If the index barely moved, say so — don't force a narrative.

Return ONLY the narrative text, no JSON."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
        )

        text = response.choices[0].message.content.strip()
        text = text.strip('"')  # Remove quotes if wrapped

        usage = response.usage
        log.info(
            "Index narrative for %s | tokens: %d in + %d out",
            index_info.get("name"), usage.prompt_tokens, usage.completion_tokens,
        )

        _idx_cache[token] = {"text": text, "ts": now}
        return text

    except Exception as e:
        log.error("Index narrative failed for %s: %s", index_info.get("name"), e)
        return None
