"""
OpenAI-powered news classifier for Indian stock market articles.
Uses gpt-4.1-mini with Structured Outputs — ONE call per cycle, accurate classification.

Pricing: $0.40 per 1M input tokens, $1.60 per 1M output tokens.
Each cycle classifies ~2-10 articles in a single API call.
"""

import json
import logging
import os
import time

from openai import OpenAI

log = logging.getLogger(__name__)

# ── Session-level cumulative stats (resets on app restart) ───────────────────
_stats = {
    "total_api_calls": 0,
    "total_articles_classified": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0.0,
}

# gpt-4.1-mini pricing per 1M tokens
_PRICE_INPUT_PER_1M = 0.40
_PRICE_OUTPUT_PER_1M = 1.60

VALID_CATEGORIES = {
    "Market Pulse",
    "Stock Alert",
    "Sector Watch",
    "IPO",
    "Global Impact",
    "Policy & Regulation",
    "Expert Opinion",
    "IRRELEVANT",
}

_SYSTEM_PROMPT = """You classify Indian stock market news. For each article, assign ONE category, ONE sentiment, and tag related NSE symbols.

Categories:
1. Market Pulse — Broad Indian market movement (Sensex/Nifty direction, FII/DII flows, market breadth)
2. Stock Alert — Specific Indian listed company (earnings, results, corporate actions, management, orders)
3. Sector Watch — Impacts entire Indian sector, not one company (auto sales, pharma bans, banking NPAs)
4. IPO — Indian IPO events (DRHP, price band, GMP, allotment, listing)
5. Global Impact — Global event moving Indian markets (Fed rates, crude oil, US tech earnings)
6. Policy & Regulation — Indian govt/regulator (RBI, SEBI, budget, GST, PLI, FDI)
7. Expert Opinion — Analyst/fund manager view on Indian markets (upgrades, targets, outlook)
8. IRRELEVANT — Zero connection to Indian investors

Sentiment (from an Indian investor's perspective):
- Bullish — clearly positive for stock/market (strong results, upgrades, rate cuts, order wins)
- Bearish — clearly negative (losses, downgrades, rate hikes, fraud, defaults)
- Neutral — factual reporting with no clear direction (appointments, filings, data without interpretation)
- Mixed — article has both positive AND negative signals, genuinely can't pick one side

Only use Mixed when truly conflicted. Most news leans one way — pick that side.

Priority: IPO > Stock Alert > Sector Watch > Policy > Expert > Market Pulse > Global > IRRELEVANT
Stocks: NSE symbols only (RELIANCE not "Reliance Industries"), max 5. Empty array if none.
When in doubt, never pick IRRELEVANT — pick the closest real category."""

# ── Structured Output schema — OpenAI enforces this, guaranteed valid JSON ───
_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "classification_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "articles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "sentiment": {"type": "string"},
                            "stocks": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["category", "sentiment", "stocks"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["articles"],
            "additionalProperties": False,
        },
    },
}


def classify_articles(articles):
    """
    Classify all articles in ONE OpenAI call using gpt-4.1-mini.
    Since we only get fresh articles per cycle (2-10), one call is enough.
    """
    if not articles:
        return articles

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        log.warning("OPENAI_API_KEY not set -- skipping classification")
        return articles

    client = OpenAI(api_key=api_key)
    user_prompt = _build_user_prompt(articles)

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=2048,
                response_format=_RESPONSE_SCHEMA,
            )

            raw = response.choices[0].message.content
            results = _parse_response(raw, len(articles))

            for idx, result in enumerate(results):
                articles[idx]["category"] = result["category"]
                articles[idx]["sentiment"] = result["sentiment"]
                articles[idx]["related_stocks"] = result["stocks"]

            # Log usage + cost
            usage = response.usage
            _stats["total_api_calls"] += 1
            _stats["total_articles_classified"] += len(articles)

            if usage:
                inp = usage.prompt_tokens
                out = usage.completion_tokens
                cost = (inp / 1_000_000 * _PRICE_INPUT_PER_1M) + (out / 1_000_000 * _PRICE_OUTPUT_PER_1M)

                _stats["total_input_tokens"] += inp
                _stats["total_output_tokens"] += out
                _stats["total_cost_usd"] += cost

                log.info(
                    "Classified %d articles | tokens: %d in + %d out | cost: $%.6f | "
                    "session total: %d calls, %d articles, $%.6f",
                    len(articles), inp, out, cost,
                    _stats["total_api_calls"],
                    _stats["total_articles_classified"],
                    _stats["total_cost_usd"],
                )
            else:
                log.info("Classified %d articles (no usage data)", len(articles))
            return articles

        except Exception as e:
            error_msg = str(e).lower()

            if any(w in error_msg for w in ("quota", "billing", "insufficient_quota")):
                log.error("OpenAI quota/billing error: %s", e)
                return articles

            status = getattr(e, "status_code", None)
            retryable = status in (429, 500, 502, 503) or "timeout" in error_msg

            if attempt == 0 and retryable:
                log.warning("OpenAI call failed (attempt 1/2, retrying in 10s): %s", e)
                time.sleep(10)
            else:
                log.error("OpenAI classification failed: %s", e)
                return articles

    return articles


def _build_user_prompt(articles):
    lines = [f"Classify these {len(articles)} articles:\n"]
    for idx, a in enumerate(articles, 1):
        lines.append(f"[{idx}] {a['title']}")
        if a.get("summary"):
            lines.append(a["summary"][:150])
        lines.append(f"-- {a['source']}")
        lines.append("")
    return "\n".join(lines)


def _parse_response(raw_text, expected_count):
    _VALID_SENTIMENTS = {"Bullish", "Bearish", "Neutral", "Mixed"}

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        log.error("Failed to parse JSON: %s", raw_text[:200])
        return [{"category": "Uncategorized", "sentiment": "", "stocks": []}] * expected_count

    results = parsed.get("articles", [])
    if not isinstance(results, list):
        log.error("Response 'articles' is not a list")
        return [{"category": "Uncategorized", "sentiment": "", "stocks": []}] * expected_count

    validated = []
    for item in results:
        if not isinstance(item, dict):
            validated.append({"category": "Uncategorized", "sentiment": "", "stocks": []})
            continue

        category = item.get("category", "Uncategorized")
        if category not in VALID_CATEGORIES:
            log.warning("Unknown category '%s' from model -- marking Uncategorized", category)
            category = "Uncategorized"

        sentiment = item.get("sentiment", "")
        if sentiment not in _VALID_SENTIMENTS:
            sentiment = ""

        stocks = item.get("stocks", [])
        if not isinstance(stocks, list):
            stocks = []
        stocks = [s.upper().strip() for s in stocks if isinstance(s, str) and s.strip()]
        stocks = stocks[:5]

        validated.append({"category": category, "sentiment": sentiment, "stocks": stocks})

    if len(validated) < expected_count:
        log.warning(
            "Model returned %d results for %d articles -- padding %d as Uncategorized",
            len(validated), expected_count, expected_count - len(validated),
        )
    while len(validated) < expected_count:
        validated.append({"category": "Uncategorized", "sentiment": "", "stocks": []})

    return validated[:expected_count]
