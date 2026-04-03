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
