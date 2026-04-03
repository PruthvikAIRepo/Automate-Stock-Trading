"""
NSE Data Service — real market breadth, FII/DII flows, and valuation metrics.

Scrapes NSE India's public JSON API endpoints.
Requires session management (visit homepage first to obtain cookies).
All data cached to respect NSE rate limits.

Data sources:
  - Breadth: /api/equity-stockIndices?index=NIFTY%20500 → advance/decline/unchanged
  - FII/DII: /api/fiidiiTradeReact → daily cash market flows
  - Valuation: /api/equity-stockIndices?index=NIFTY%2050 → PE, PB, Dividend Yield
"""

import logging
import time
from datetime import datetime

import requests

log = logging.getLogger(__name__)

# ─── NSE Session Management ──────────────────────────────────────────────────
# NSE blocks requests without valid cookies from a homepage visit.
# We maintain a session and refresh it every 5 minutes.

_session = None
_session_ts = 0
_SESSION_MAX_AGE = 300  # seconds

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # NOTE: Don't include Accept-Encoding: br — Python requests can't decode brotli.
    # Let requests handle gzip/deflate automatically.
    "Connection": "keep-alive",
}

# Headers specifically for API calls (after cookies are established)
_API_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.nseindia.com/market-data/live-equity-market",
}


def _get_session():
    """Get or create a session with fresh NSE cookies."""
    global _session, _session_ts
    now = time.time()

    if _session and (now - _session_ts) < _SESSION_MAX_AGE:
        return _session

    s = requests.Session()
    s.headers.update(_HEADERS)

    try:
        # Step 1: Hit homepage to get initial cookies (don't raise on status)
        resp = s.get("https://www.nseindia.com", timeout=10, allow_redirects=True)
        if not s.cookies:
            # Try alternative entry point
            s.get("https://www.nseindia.com/market-data/live-equity-market", timeout=10)

        if s.cookies:
            _session = s
            _session_ts = now
            log.debug("NSE session established (cookies: %d)", len(s.cookies))
        else:
            log.warning("NSE session got no cookies (status: %d)", resp.status_code)
            return None

    except Exception as e:
        log.warning("Failed to init NSE session: %s", e)
        return None

    return _session


def _nse_get(path):
    """Make an authenticated request to NSE's API."""
    session = _get_session()
    if not session:
        return None

    url = f"https://www.nseindia.com{path}"
    try:
        resp = session.get(url, headers=_API_HEADERS, timeout=10)

        # Cookie expired — refresh and retry once
        if resp.status_code in (401, 403):
            global _session_ts
            _session_ts = 0
            session = _get_session()
            if not session:
                return None
            resp = session.get(url, headers=_API_HEADERS, timeout=10)

        if resp.status_code != 200:
            log.warning("NSE API returned %d for %s", resp.status_code, path)
            return None

        return resp.json()

    except requests.exceptions.JSONDecodeError:
        log.error("NSE returned non-JSON for %s (status %s)", path, resp.status_code)
        return None
    except Exception as e:
        log.error("NSE API error (%s): %s", path, e)
        return None


# ─── Cache ────────────────────────────────────────────────────────────────────

_cache = {}


def _cached(key, ttl):
    """Return cached data if still fresh, else None."""
    if key in _cache:
        entry = _cache[key]
        if time.time() - entry["ts"] < ttl:
            return entry["data"]
    return None


def _set_cache(key, data):
    _cache[key] = {"data": data, "ts": time.time()}


# ─── Public API ───────────────────────────────────────────────────────────────

def _fetch_all_indices():
    """
    Fetch /api/allIndices — single call that returns PE/PB/DY + advance/decline
    for ALL NSE indices. This is our primary NSE data source.
    Cached for 60 seconds.
    """
    cached = _cached("all_indices", 60)
    if cached:
        return cached

    data = _nse_get("/api/allIndices")
    if not data:
        return None

    _set_cache("all_indices", data)
    return data


def fetch_market_breadth():
    """
    Fetch real advance / decline / unchanged from NSE (broad market).

    Returns:
        dict with keys: advances, declines, unchanged, total, adv_pct, dec_pct, unch_pct
        None if NSE is unavailable.
    """
    cached = _cached("breadth", 60)
    if cached:
        return cached

    data = _fetch_all_indices()
    if not data:
        return None

    try:
        # Top-level advance/decline covers the entire NSE market
        advances = int(data.get("advances", 0))
        declines = int(data.get("declines", 0))
        unchanged = int(data.get("unchanged", 0))
        total = advances + declines + unchanged

        if total == 0:
            log.warning("NSE breadth total is 0 — data may be stale")
            return None

        result = {
            "advances": advances,
            "declines": declines,
            "unchanged": unchanged,
            "total": total,
            "adv_pct": round(advances / total * 100, 1),
            "dec_pct": round(declines / total * 100, 1),
            "unch_pct": round(unchanged / total * 100, 1),
        }

        _set_cache("breadth", result)
        log.info(
            "NSE breadth: %d up / %d down / %d flat (%.0f%% advancing)",
            advances, declines, unchanged, result["adv_pct"],
        )
        return result

    except (KeyError, ValueError, TypeError) as e:
        log.error("Failed to parse NSE breadth: %s | raw keys: %s", e, list(data.keys()))
        return None


def fetch_fii_dii():
    """
    Fetch today's FII/DII cash-market activity from NSE.

    Returns:
        dict with keys: fii_buy, fii_sell, fii_net, dii_buy, dii_sell, dii_net, date
        None if NSE is unavailable.
    """
    cached = _cached("fii_dii", 300)  # 5-min cache
    if cached:
        return cached

    data = _nse_get("/api/fiidiiTradeReact")
    if not data or not isinstance(data, list):
        return None

    try:
        result = {"date": None}

        for entry in data:
            category = entry.get("category", "").upper()
            date_str = entry.get("date", "")

            # Parse values — NSE sometimes includes commas in numbers
            buy = float(str(entry.get("buyValue", "0")).replace(",", ""))
            sell = float(str(entry.get("sellValue", "0")).replace(",", ""))
            net = float(str(entry.get("netValue", "0")).replace(",", ""))

            if not result["date"] and date_str:
                result["date"] = date_str

            if "FII" in category or "FPI" in category:
                result["fii_buy"] = round(buy, 2)
                result["fii_sell"] = round(sell, 2)
                result["fii_net"] = round(net, 2)
            elif "DII" in category:
                result["dii_buy"] = round(buy, 2)
                result["dii_sell"] = round(sell, 2)
                result["dii_net"] = round(net, 2)

        # Must have both FII and DII
        if "fii_net" not in result or "dii_net" not in result:
            log.warning("NSE FII/DII incomplete: got keys %s", list(result.keys()))
            return None

        _set_cache("fii_dii", result)
        log.info(
            "NSE FII/DII (%s): FII net ₹%.0f Cr, DII net ₹%.0f Cr",
            result["date"], result["fii_net"], result["dii_net"],
        )
        return result

    except (KeyError, ValueError, TypeError) as e:
        log.error("Failed to parse NSE FII/DII: %s", e)
        return None


def fetch_nifty_valuation():
    """
    Fetch Nifty 50 PE, PB, and Dividend Yield from NSE /api/allIndices.

    Returns:
        dict with keys: pe, pb, dy
        None if unavailable.
    """
    cached = _cached("valuation", 300)  # 5-min cache
    if cached:
        return cached

    data = _fetch_all_indices()
    if not data:
        return None

    try:
        # Search for NIFTY 50 in the data array
        for item in data.get("data", []):
            idx_name = str(item.get("index", "")).upper()
            if idx_name == "NIFTY 50":
                pe = float(item.get("pe", 0) or 0)
                pb = float(item.get("pb", 0) or 0)
                dy = float(item.get("dy", 0) or 0)

                if pe == 0:
                    log.warning("NSE returned PE=0 for Nifty 50")
                    return None

                result = {
                    "pe": round(pe, 2),
                    "pb": round(pb, 2),
                    "dy": round(dy, 2),
                }

                _set_cache("valuation", result)
                log.info("Nifty 50 valuation: PE=%.2f, PB=%.2f, DY=%.2f%%", pe, pb, dy)
                return result

        log.warning("NIFTY 50 not found in NSE allIndices data")
        return None

    except (KeyError, ValueError, TypeError) as e:
        log.error("Failed to parse Nifty valuation: %s", e)
        return None


# ─── Index PE & Breadth from allIndices ──────────────────────────────────────

def fetch_index_pe_and_breadth(nse_name):
    """
    Get PE ratio and advance/decline for a specific index from allIndices.
    Returns: {"pe": float, "pb": float, "dy": float, "advances": int, "declines": int, "unchanged": int} or None
    """
    data = _fetch_all_indices()
    if not data:
        return None

    target = nse_name.upper()
    for item in data.get("data", []):
        idx_name = str(item.get("index", "")).upper()
        if idx_name == target:
            pe = float(item.get("pe", 0) or 0)
            pb = float(item.get("pb", 0) or 0)
            dy = float(item.get("dy", 0) or 0)
            adv = int(item.get("advances", 0) or 0)
            dec = int(item.get("declines", 0) or 0)
            unch = int(item.get("unchanged", 0) or 0)
            return {
                "pe": round(pe, 2) if pe else None,
                "pb": round(pb, 2) if pb else None,
                "dy": round(dy, 2) if dy else None,
                "advances": adv,
                "declines": dec,
                "unchanged": unch,
                "total": adv + dec + unch,
            }
    return None


# Angel One name → NSE allIndices name for PE/breadth lookup
_HERO_NSE_MAP = {
    "NIFTY": "NIFTY 50",
    "BANKNIFTY": "NIFTY BANK",
}


# ─── Index Constituents ──────────────────────────────────────────────────────

# Angel One symbol → NSE index name for constituent lookup
_CONSTITUENT_INDEX_MAP = {
    "NIFTY":             "NIFTY 50",
    "NIFTY 50":          "NIFTY 50",
    "BANKNIFTY":         "NIFTY BANK",
    "NIFTY BANK":        "NIFTY BANK",
    "NIFTY NEXT 50":     "NIFTY NEXT 50",
    "NIFTY IT":          "NIFTY IT",
    "NIFTY FIN SERVICE": "NIFTY FINANCIAL SERVICES",
    "NIFTY FMCG":        "NIFTY FMCG",
    "NIFTY PHARMA":      "NIFTY PHARMA",
    "NIFTY AUTO":        "NIFTY AUTO",
    "NIFTY ENERGY":      "NIFTY ENERGY",
    "NIFTY METAL":       "NIFTY METAL",
    "NIFTY REALTY":      "NIFTY REALTY",
    "NIFTY INFRA":       "NIFTY INFRASTRUCTURE",
    "NIFTY PSU BANK":    "NIFTY PSU BANK",
    "NIFTY PVT BANK":    "NIFTY PRIVATE BANK",
    "NIFTY MEDIA":       "NIFTY MEDIA",
    "NIFTY MID SELECT":  "NIFTY MIDCAP SELECT",
    "NIFTY MIDCAP 50":   "NIFTY MIDCAP 50",
    "NIFTY MIDCAP 100":  "NIFTY MIDCAP 100",
    "NIFTY SMLCAP 50":   "NIFTY SMLCAP 50",
    "NIFTY SMLCAP 100":  "NIFTY SMALLCAP 100",
    "NIFTY SMLCAP 250":  "NIFTY SMALLCAP 250",
    "NIFTY 100":         "NIFTY 100",
    "NIFTY 200":         "NIFTY 200",
    "NIFTY 500":         "NIFTY 500",
    "NIFTY COMMODITIES": "NIFTY COMMODITIES",
    "NIFTY CONSUMPTION": "NIFTY CONSUMPTION",
    "NIFTY CPSE":        "NIFTY CPSE",
    "NIFTY GROWSECT 15": "NIFTY GROWSECT 15",
    "NIFTY SERV SECTOR": "NIFTY SERVICES SECTOR",
    "NIFTY MNC":         "NIFTY MNC",
    "NIFTY DIV OPPS 50": "NIFTY DIVIDEND OPPORTUNITIES 50",
    "NIFTY100 QUALITY 30": "NIFTY100 QUALITY 30",
    "NIFTY MIDCAP 150":  "NIFTY MIDCAP 150",
    "NIFTY HEALTHCARE":  "NIFTY HEALTHCARE INDEX",
    "NIFTY OIL AND GAS": "NIFTY OIL & GAS",
}


def fetch_index_constituents(angel_name):
    """
    Fetch constituent stocks of an NSE index.

    Args:
        angel_name: Index name as shown in Angel One (e.g., "NIFTY", "BANKNIFTY")

    Returns:
        dict with keys:
            stocks: list of constituent dicts (symbol, name, sector, ltp, change, change_pct, ...)
            top_gainers: top 5 by change_pct
            top_losers: bottom 5 by change_pct
            sector_breakdown: dict {sector: {count, avg_change, stocks}}
            total: int
        None if unavailable
    """
    nse_name = _CONSTITUENT_INDEX_MAP.get(angel_name.upper())
    if not nse_name:
        # Try direct lookup
        nse_name = angel_name

    cache_key = f"constituents_{nse_name}"
    cached = _cached(cache_key, 120)  # 2-min cache
    if cached:
        return cached

    import urllib.parse
    path = f"/api/equity-stockIndices?index={urllib.parse.quote(nse_name)}"
    data = _nse_get(path)

    if not data or "data" not in data:
        return None

    try:
        stocks = []
        for item in data["data"]:
            # First entry is often the index summary — skip it
            symbol = item.get("symbol", "")
            if not symbol or symbol == nse_name:
                continue

            # Skip if it looks like an index entry (no series)
            if not item.get("series"):
                continue

            sector = ""
            meta = item.get("meta", {})
            if meta:
                sector = meta.get("industry", "") or meta.get("sector", "")

            stocks.append({
                "symbol": symbol,
                "name": meta.get("companyName", symbol) if meta else symbol,
                "sector": sector,
                "ltp": float(item.get("lastPrice", 0) or 0),
                "change": float(item.get("change", 0) or 0),
                "change_pct": float(item.get("pChange", 0) or 0),
                "open": float(item.get("open", 0) or 0),
                "high": float(item.get("dayHigh", 0) or 0),
                "low": float(item.get("dayLow", 0) or 0),
                "prev_close": float(item.get("previousClose", 0) or 0),
                "volume": int(item.get("totalTradedVolume", 0) or 0),
                "year_high": float(item.get("yearHigh", 0) or 0),
                "year_low": float(item.get("yearLow", 0) or 0),
            })

        if not stocks:
            return None

        # Approximate point contribution per stock
        # Method: distribute index change proportionally to each stock's
        # price-weighted change (larger stocks contribute more points)
        # weight_proxy = stock_ltp (higher priced stocks generally have higher weights)
        total_weighted = sum(s["ltp"] * abs(s["change_pct"]) for s in stocks if s["ltp"] > 0)
        index_change = float(data.get("metadata", {}).get("change", 0) or 0)

        if total_weighted > 0 and index_change != 0:
            for s in stocks:
                if s["ltp"] > 0:
                    weight_share = (s["ltp"] * abs(s["change_pct"])) / total_weighted
                    s["pts_contribution"] = round(index_change * weight_share * (1 if s["change_pct"] >= 0 else -1), 1)
                else:
                    s["pts_contribution"] = 0
        else:
            for s in stocks:
                s["pts_contribution"] = 0

        # Sort by change_pct for gainers/losers
        sorted_by_change = sorted(stocks, key=lambda s: s["change_pct"], reverse=True)
        top_gainers = [s for s in sorted_by_change if s["change_pct"] > 0][:5]
        top_losers = [s for s in reversed(sorted_by_change) if s["change_pct"] < 0][:5]

        # Top contributors/detractors by point impact
        sorted_by_pts = sorted(stocks, key=lambda s: s["pts_contribution"], reverse=True)
        top_contributors = [s for s in sorted_by_pts if s["pts_contribution"] > 0][:5]
        top_detractors = [s for s in reversed(sorted_by_pts) if s["pts_contribution"] < 0][:5]

        # Sector breakdown
        sector_map = {}
        for s in stocks:
            sec = s["sector"] or "Other"
            if sec not in sector_map:
                sector_map[sec] = {"count": 0, "total_change": 0, "stocks": []}
            sector_map[sec]["count"] += 1
            sector_map[sec]["total_change"] += s["change_pct"]
            sector_map[sec]["stocks"].append(s["symbol"])

        sector_breakdown = {}
        for sec, info in sector_map.items():
            sector_breakdown[sec] = {
                "count": info["count"],
                "avg_change": round(info["total_change"] / info["count"], 2),
                "stocks": info["stocks"],
            }

        # Sort sectors by count (largest first)
        sector_breakdown = dict(
            sorted(sector_breakdown.items(), key=lambda x: x[1]["count"], reverse=True)
        )

        result = {
            "stocks": stocks,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "top_contributors": top_contributors,
            "top_detractors": top_detractors,
            "index_change_pts": round(index_change, 2),
            "sector_breakdown": sector_breakdown,
            "total": len(stocks),
        }

        _set_cache(cache_key, result)
        log.info("NSE constituents for %s: %d stocks", nse_name, len(stocks))
        return result

    except Exception as e:
        log.error("Failed to parse NSE constituents for %s: %s", nse_name, e)
        return None


# ─── Utility ──────────────────────────────────────────────────────────────────

def is_market_hours():
    """Check if NSE is currently in trading hours (Mon-Fri, 9:00-15:45 IST)."""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 900 <= t <= 1545


def is_pre_market():
    """Pre-market session: 8:30 - 9:15 IST."""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 830 <= t < 915
