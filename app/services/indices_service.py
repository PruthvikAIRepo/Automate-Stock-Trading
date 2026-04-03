"""
Indices Data Service — fetches real index data from Angel One SmartAPI.

Responsibilities:
- Fetch live quotes for all indices (FULL mode → LTP, OHLC, change, volume, 52W)
- Fetch historical candle data for charts
- Compute market breadth (advance/decline) from hero index constituents
- Format everything for the Jinja2 template
- Graceful fallback to dummy data if API unavailable

Rate limits respected:
- getMarketData: 1 req/sec, max 50 tokens per request
- getCandleData: ~3 req/sec
"""

import logging
import time
from datetime import datetime, timedelta

from app.services.angel_auth import get_angel_auth
from app.services.scripmaster import get_index_tokens, SECTORAL_INDEX_TOKENS, VIX_TOKEN

log = logging.getLogger(__name__)

# ─── KEY INDICES STRIP — shown in horizontal scroll at top ────────────────
# Order matters: this is the display order in the strip
KEY_INDEX_TOKENS = (
    "99926000",  # NIFTY 50
    "99926009",  # BANK NIFTY
    "99919000",  # SENSEX
    "99926037",  # NIFTY FIN SERVICE
    "99926008",  # NIFTY IT
    "99926011",  # NIFTY MIDCAP 100
    "99926032",  # NIFTY SMLCAP 100
    "99926013",  # NIFTY NEXT 50
    "99926004",  # NIFTY 500
)

# ─── POPULAR & NICHE INDEX CLASSIFICATION ───────────────────────────────────
# Popular: indices that a common investor follows daily
POPULAR_TOKENS = {
    # NSE Broad
    "99926000", "99926013", "99926012", "99926033", "99926004",  # Nifty 50, Next50, 100, 200, 500
    "99926014", "99926011", "99926060",  # Midcap 50, Midcap 100, Midcap 150
    "99926061", "99926032", "99926062",  # Smlcap 50, 100, 250
    # NSE Sectoral
    "99926009", "99926037", "99926047",  # Bank, Fin Svc, Pvt Bank
    "99926008", "99926029", "99926023",  # IT, Auto, Pharma
    "99926021", "99926020", "99926030",  # FMCG, Energy, Metal
    "99926018", "99926025", "99926019",  # Realty, PSU Bank, Infra
    "99926031", "99926026",              # Media, Serv Sector
    # BSE Broad
    "99919000", "99919002", "99919003", "99919004",  # Sensex, BSE100, 200, 500
    "99919016", "99919017", "99919042",  # Midcap, Smallcap, Largecap
    "99919082", "99919083",              # Sensex 50, Sensex Next 50
    # BSE Sectoral
    "99919012", "99919005", "99919013",  # Bankex, BSE IT, Auto
    # MCX
    "99920003", "99920002", "99920000",  # Gold, Silver, Crude
}

# Niche: confusing for common investors — hide from default, show only in "All"
NICHE_KEYWORDS = [
    "PR 1X INV", "TR 1X INV", "PR 2X LEV", "TR 2X LEV",  # Leveraged / Inverse
    "DIV POINT",                                            # Dividend point
    "GS 10YR", "GS 4 8YR", "GS 8 13YR", "GS 11 15YR",   # Govt securities
    "GS 15YRPLUS", "GS COMPSITE", "GS 10YR CLN",
    "HANGSENG", "BEES-NAV",                                 # ETF NAV
    "DOL30", "DOL100", "DOL200",                            # Dollar-denominated
]


def _is_niche(symbol):
    """Check if an index is niche/confusing for common investors."""
    upper = symbol.upper()
    return any(kw in upper for kw in NICHE_KEYWORDS)


# ─── SPARKLINE GENERATION ────────────────────────────────────────────────────

def _sparkline_svg(candles):
    """Generate an SVG sparkline from historical candle data."""
    if not candles or len(candles) < 2:
        return ""

    closes = [c[4] for c in candles[-10:]]
    if not closes:
        return ""

    mn, mx = min(closes), max(closes)
    rng = mx - mn if mx != mn else 1
    w, h = 64, 24

    pts = []
    for i, val in enumerate(closes):
        x = (i / (len(closes) - 1)) * (w - 1)
        y = h - 2 - ((val - mn) / rng) * (h - 4)
        pts.append(f"{x:.1f},{y:.1f}")

    is_positive = closes[-1] >= closes[0]
    color = "#00D09C" if is_positive else "#EF4444"
    points = " ".join(pts)

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none">'
        f'<polyline points="{points}" stroke="{color}" stroke-width="1.5" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


def _dummy_sparkline(is_positive):
    """Fallback sparkline when no historical data available."""
    import random
    pts = []
    y = 12
    for i in range(10):
        y += random.uniform(-4, 3) if is_positive else random.uniform(-3, 4)
        y = max(2, min(22, y))
        pts.append(f"{i * 7},{y:.1f}")
    color = "#00D09C" if is_positive else "#EF4444"
    return (
        f'<svg width="64" height="24" viewBox="0 0 63 24" fill="none">'
        f'<polyline points="{" ".join(pts)}" stroke="{color}" stroke-width="1.5" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


# ─── LIVE DATA FETCHING ─────────────────────────────────────────────────────

def _batch_fetch_quotes(tokens_by_exchange):
    """
    Fetch quotes in batches of 50 (Angel One limit per request).
    Returns: dict {token: quote_data}
    """
    auth = get_angel_auth()
    all_quotes = {}

    for exchange, tokens in tokens_by_exchange.items():
        for i in range(0, len(tokens), 50):
            batch = tokens[i:i + 50]
            result = auth.get_market_data("FULL", {exchange: batch})
            if result:
                for quote in result:
                    all_quotes[str(quote.get("symbolToken", ""))] = quote

            if i + 50 < len(tokens):
                time.sleep(1.1)

    return all_quotes


def _format_index(token_info, quote=None, sparkline_html=""):
    """Format a single index for the template."""
    if quote:
        ltp = float(quote.get("ltp", 0))
        change = float(quote.get("netChange", 0))
        change_pct = float(quote.get("percentChange", 0))
        open_price = float(quote.get("open", 0))
        high = float(quote.get("high", 0))
        low = float(quote.get("low", 0))
        close = float(quote.get("close", 0))
        volume = int(quote.get("tradeVolume", 0))
        low_52w = float(quote.get("52WeekLow", 0))
        high_52w = float(quote.get("52WeekHigh", 0))

        token = token_info["token"]
        return {
            "token": token,
            "name": token_info.get("name", token_info.get("symbol", "")),
            "symbol": token_info.get("symbol", ""),
            "exchange": token_info.get("exchange", "NSE"),
            "category": token_info.get("category", "thematic"),
            "value": ltp,
            "change": change,
            "change_pct": round(change_pct, 2),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "low_52w": low_52w,
            "high_52w": high_52w,
            "sparkline": sparkline_html or _dummy_sparkline(change >= 0),
            "is_popular": token in POPULAR_TOKENS,
            "is_niche": _is_niche(token_info.get("symbol", "")),
            "live": True,
        }
    else:
        return {
            "token": token_info.get("token", ""),
            "name": token_info.get("name", token_info.get("symbol", "")),
            "symbol": token_info.get("symbol", ""),
            "exchange": token_info.get("exchange", "NSE"),
            "category": token_info.get("category", "thematic"),
            "value": 0, "change": 0, "change_pct": 0,
            "open": 0, "high": 0, "low": 0, "close": 0,
            "volume": 0, "low_52w": 0, "high_52w": 0,
            "sparkline": "", "is_popular": False, "is_niche": False,
            "live": False,
        }


# ─── 52-WEEK RANGE FROM HISTORICAL DATA ─────────────────────────────────────

def compute_52w_from_candles(candles):
    """
    Compute 52-week high/low from daily candle data.
    Angel One returns 0 for 52WeekHigh/Low on index tokens (AMXIDX),
    so we calculate from getCandleData instead.

    candles: list of [DateTime, O, H, L, C, Volume] from Angel One
    Returns: {"high": float, "low": float} or None
    """
    if not candles or len(candles) < 5:
        return None

    try:
        highs = [float(c[2]) for c in candles if float(c[2]) > 0]
        lows = [float(c[3]) for c in candles if float(c[3]) > 0]

        if not highs or not lows:
            return None

        return {
            "high": max(highs),
            "low": min(lows),
        }
    except (IndexError, ValueError, TypeError):
        return None


def fetch_52w_for_index(token, exchange="NSE"):
    """Fetch 52-week high/low for a single index by computing from 1-year daily candles."""
    candles = fetch_index_history(token, exchange, "ONE_DAY", days=365)
    return compute_52w_from_candles(candles)


# ─── PUBLIC API ──────────────────────────────────────────────────────────────

def fetch_all_indices():
    """
    Fetch live data for all indices.

    Returns dict with:
        all_table: flat list of ALL live indices (for sortable table)
        popular: subset of all_table where is_popular=True
        hero: [NIFTY 50, BANK NIFTY]
        vix: formatted VIX dict or None
        sector_performance: sectoral indices sorted by change%
        total: int (live count)
        live: bool
    """
    token_data = get_index_tokens()
    all_indices = token_data.get("all", [])

    if not all_indices:
        log.warning("No index tokens available — returning empty data")
        return _fallback_indices()

    # Group tokens by exchange for batch fetching
    tokens_by_exchange = {}
    for idx in all_indices:
        exchange = idx["exchange"]
        tokens_by_exchange.setdefault(exchange, []).append(idx["token"])

    # Also add VIX
    if token_data.get("vix"):
        vix = token_data["vix"]
        tokens_by_exchange.setdefault(vix["exchange"], []).append(vix["token"])

    # Fetch live quotes
    auth = get_angel_auth()
    quotes = {}
    is_live = False

    if auth.is_configured:
        quotes = _batch_fetch_quotes(tokens_by_exchange)
        is_live = len(quotes) > 0
        if is_live:
            log.info("Fetched live quotes for %d indices", len(quotes))
        else:
            log.warning("API returned no quotes — falling back to dummy data")

    if not is_live:
        return _fallback_indices()

    # Build flat table of all live indices
    all_table = []
    hero = []
    vix_data = None

    for idx in all_indices:
        token = idx["token"]
        quote = quotes.get(token)

        # Skip indices with no data or zero LTP
        if not quote or float(quote.get("ltp", 0)) == 0:
            continue

        # Skip VIX from the table — it's shown in Fear Level card only
        if token == VIX_TOKEN:
            continue

        formatted = _format_index(idx, quote)
        all_table.append(formatted)

        # Key indices strip — top indices investors check first
        if token in KEY_INDEX_TOKENS:
            hero.append(formatted)

    # VIX — separate from table
    if token_data.get("vix"):
        vix_quote = quotes.get(VIX_TOKEN)
        if vix_quote:
            vix_data = _format_index(token_data["vix"], vix_quote)

    # Sector performance — sorted by change%, with LTP
    sector_perf = []
    for token, name in SECTORAL_INDEX_TOKENS.items():
        quote = quotes.get(token)
        if quote:
            sector_perf.append({
                "name": name,
                "token": token,
                "value": float(quote.get("ltp", 0)),
                "change": float(quote.get("netChange", 0)),
                "change_pct": round(float(quote.get("percentChange", 0)), 2),
            })
    sector_perf.sort(key=lambda x: x["change_pct"], reverse=True)

    # Sort table by value (largest first) as default
    all_table.sort(key=lambda x: x["value"], reverse=True)

    # Popular subset
    popular = [x for x in all_table if x["is_popular"]]
    popular.sort(key=lambda x: x["value"], reverse=True)

    # Sort key indices in priority order
    _key_order = {t: i for i, t in enumerate(KEY_INDEX_TOKENS)}
    hero.sort(key=lambda x: _key_order.get(x["token"], 99))

    # Real sparklines for first 2 hero indices only (NIFTY, BANKNIFTY — 365-day candles)
    for h in hero[:2]:
        try:
            candles = fetch_index_history(h["token"], h["exchange"], "ONE_DAY", days=365)
            if candles and len(candles) >= 2:
                h["sparkline"] = _sparkline_svg(candles)
                w52 = compute_52w_from_candles(candles)
                if w52:
                    h["low_52w"] = w52["low"]
                    h["high_52w"] = w52["high"]
        except Exception:
            pass

    return {
        "all_table": all_table,
        "popular": popular,
        "hero": hero,
        "vix": vix_data,
        "sector_performance": sector_perf,
        "total": len(all_table),
        "total_popular": len(popular),
        "live": True,
    }


def fetch_sector_timeframe_returns(sector_perf):
    """
    Compute 1W, 1M, 3M returns for each sectoral index.
    Fetches 90-day daily candles per sector and extracts historical closes.
    Cached for 10 minutes to avoid excessive API calls.

    Args:
        sector_perf: list of dicts with token, name, value (current LTP)

    Returns:
        dict {token: {"1W": float, "1M": float, "3M": float}}
    """
    import threading

    cache_key = "sector_tf_returns"
    cached = None
    now = time.time()

    # Simple module-level cache
    if hasattr(fetch_sector_timeframe_returns, "_cache"):
        c = fetch_sector_timeframe_returns._cache
        if c and (now - c.get("ts", 0)) < 600:
            cached = c.get("data")
    if cached:
        return cached

    results = {}

    for sec in sector_perf:
        token = sec["token"]
        current = sec["value"]
        if current <= 0:
            continue

        try:
            candles = fetch_index_history(token, "NSE", "ONE_DAY", days=180)
            if not candles or len(candles) < 5:
                continue

            # candles: [DateTime, O, H, L, C, Vol] — most recent last
            closes = [(c[0], float(c[4])) for c in candles if float(c[4]) > 0]
            if len(closes) < 5:
                continue

            total = len(closes)
            tf = {}

            # 1W ≈ 5 trading days
            if total >= 5:
                old_close = closes[-5][1]
                tf["1W"] = round((current - old_close) / old_close * 100, 2)

            # 1M ≈ 22 trading days
            if total >= 22:
                old_close = closes[-22][1]
                tf["1M"] = round((current - old_close) / old_close * 100, 2)

            # 3M ≈ 66 trading days
            if total >= 66:
                old_close = closes[-66][1]
                tf["3M"] = round((current - old_close) / old_close * 100, 2)

            # 6M ≈ 132 trading days
            if total >= 132:
                old_close = closes[-132][1]
                tf["6M"] = round((current - old_close) / old_close * 100, 2)

            results[token] = tf

        except Exception:
            continue

        # Respect rate limits (getCandleData: ~3 req/sec)
        time.sleep(0.35)

    # Cache results
    fetch_sector_timeframe_returns._cache = {"data": results, "ts": now}
    log.info("Sector timeframe returns: computed for %d/%d sectors", len(results), len(sector_perf))
    return results


def fetch_index_history(token, exchange="NSE", interval="ONE_DAY", days=365):
    """Fetch historical candle data for a specific index."""
    auth = get_angel_auth()
    if not auth.is_configured:
        return []

    now = datetime.now()
    from_date = (now - timedelta(days=days)).strftime("%Y-%m-%d 09:15")
    to_date = now.strftime("%Y-%m-%d 15:30")

    params = {
        "exchange": exchange,
        "symboltoken": token,
        "interval": interval,
        "fromdate": from_date,
        "todate": to_date,
    }

    candles = auth.get_candle_data(params)
    return candles if candles else []


# ─── PIVOT LEVELS ─────────────────────────────────────────────────────────────

def compute_pivot_levels(token, exchange="NSE"):
    """
    Calculate classic pivot points from the previous trading day's OHLC.

    Returns dict with P, R1, R2, R3, S1, S2, S3 or None if data unavailable.
    Formula (Classic/Floor Pivots — used by 90% of F&O traders):
        P  = (prevH + prevL + prevC) / 3
        R1 = 2*P - prevL          S1 = 2*P - prevH
        R2 = P + (prevH - prevL)  S2 = P - (prevH - prevL)
        R3 = prevH + 2*(P-prevL)  S3 = prevL - 2*(prevH - P)
    """
    try:
        candles = fetch_index_history(token, exchange, "ONE_DAY", days=5)
        if not candles or len(candles) < 2:
            return None

        # Last candle may be today's incomplete candle — use second-to-last
        prev = candles[-2]
        h = float(prev[2])  # High
        l = float(prev[3])  # Low
        c = float(prev[4])  # Close

        if h == 0 or l == 0 or c == 0:
            return None

        p = (h + l + c) / 3
        r1 = 2 * p - l
        r2 = p + (h - l)
        r3 = h + 2 * (p - l)
        s1 = 2 * p - h
        s2 = p - (h - l)
        s3 = l - 2 * (h - p)

        return {
            "P": round(p, 2),
            "R1": round(r1, 2), "R2": round(r2, 2), "R3": round(r3, 2),
            "S1": round(s1, 2), "S2": round(s2, 2), "S3": round(s3, 2),
            "prev_high": round(h, 2), "prev_low": round(l, 2), "prev_close": round(c, 2),
        }
    except Exception as e:
        log.error("Pivot calculation failed for %s: %s", token, e)
        return None


# ─── FALLBACK ────────────────────────────────────────────────────────────────

def _fallback_indices():
    """Return dummy data when API is unavailable."""
    from app.dummy_data import ALL_INDICES, MARKET_BREADTH, FII_DII

    broad = ALL_INDICES.get("broad_market", [])
    sectoral = ALL_INDICES.get("sectoral", [])
    thematic = ALL_INDICES.get("thematic", [])

    for idx_list in [broad, sectoral, thematic]:
        for idx in idx_list:
            idx.setdefault("token", "")
            idx.setdefault("symbol", idx.get("name", ""))
            idx.setdefault("exchange", "NSE")
            idx.setdefault("category", "broad_market")
            idx.setdefault("open", idx.get("value", 0))
            idx.setdefault("high", idx.get("value", 0) * 1.005)
            idx.setdefault("low", idx.get("value", 0) * 0.995)
            idx.setdefault("close", idx.get("value", 0))
            idx.setdefault("volume", 0)
            idx.setdefault("low_52w", idx.get("value", 0) * 0.8)
            idx.setdefault("high_52w", idx.get("value", 0) * 1.15)
            idx.setdefault("is_popular", True)
            idx.setdefault("is_niche", False)
            idx.setdefault("live", False)

    all_table = broad + sectoral + thematic
    all_table.sort(key=lambda x: x.get("value", 0), reverse=True)

    nifty50 = next((i for i in broad if i.get("name", "") == "NIFTY 50"), None)
    banknifty = next((i for i in sectoral if "BANK" in i.get("name", "") and "PSU" not in i.get("name", "")), None)
    hero = [x for x in [nifty50, banknifty] if x]

    vix = {
        "name": "INDIA VIX", "symbol": "INDIA VIX", "token": VIX_TOKEN,
        "exchange": "NSE", "value": 14.5, "change": -0.3, "change_pct": -2.03,
        "live": False,
    }

    sector_perf = []
    for idx in sectoral[:10]:
        sector_perf.append({
            "name": idx["name"], "token": idx.get("token", ""),
            "value": idx["value"], "change": idx["change"],
            "change_pct": idx["change_pct"],
        })
    sector_perf.sort(key=lambda x: x["change_pct"], reverse=True)

    return {
        "all_table": all_table,
        "popular": all_table,
        "hero": hero,
        "vix": vix,
        "sector_performance": sector_perf,
        "total": len(all_table),
        "total_popular": len(all_table),
        "live": False,
    }


def get_market_context():
    """
    Get real market context — breadth, FII/DII, valuation from NSE.
    Falls back to dummy data if NSE is unavailable.
    """
    from app.dummy_data import MARKET_BREADTH as DUMMY_BREADTH, FII_DII as DUMMY_FII_DII

    try:
        from app.services.nse_data import fetch_market_breadth, fetch_fii_dii, fetch_nifty_valuation

        breadth = fetch_market_breadth() or DUMMY_BREADTH
        fii_dii = fetch_fii_dii() or DUMMY_FII_DII
        valuation = fetch_nifty_valuation()  # None is OK — template handles it

        # Tag whether data is real or dummy
        if breadth is not DUMMY_BREADTH:
            breadth["live"] = True
        if fii_dii is not DUMMY_FII_DII:
            fii_dii["live"] = True

    except Exception as e:
        log.error("NSE data fetch failed, using dummy: %s", e)
        breadth = DUMMY_BREADTH
        fii_dii = DUMMY_FII_DII
        valuation = None

    return {
        "breadth": breadth,
        "fii_dii": fii_dii,
        "valuation": valuation,
    }
