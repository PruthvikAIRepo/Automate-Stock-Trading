"""
Global Markets Service — live data for world indices.

Fetches Dow Jones, Nasdaq, S&P 500, Nikkei 225, Hang Seng, FTSE 100
from Yahoo Finance's public chart API.

All symbols fetched in parallel (~1-2s total).
Cached for 5 minutes to avoid rate limits.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

log = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

GLOBAL_INDICES = [
    {"symbol": "^DJI",   "name": "Dow Jones",  "desc": "US (30 companies)",  "flag": "\U0001f1fa\U0001f1f8"},
    {"symbol": "^IXIC",  "name": "Nasdaq",      "desc": "US Tech",            "flag": "\U0001f1fa\U0001f1f8"},
    {"symbol": "^GSPC",  "name": "S&P 500",     "desc": "US (500 companies)", "flag": "\U0001f1fa\U0001f1f8"},
    {"symbol": "^N225",  "name": "Nikkei 225",  "desc": "Japan",              "flag": "\U0001f1ef\U0001f1f5"},
    {"symbol": "^HSI",   "name": "Hang Seng",   "desc": "Hong Kong",          "flag": "\U0001f1ed\U0001f1f0"},
    {"symbol": "^FTSE",  "name": "FTSE 100",    "desc": "UK",                 "flag": "\U0001f1ec\U0001f1e7"},
    {"symbol": "^STOXX50E", "name": "Euro Stoxx 50", "desc": "Europe",        "flag": "\U0001f1ea\U0001f1fa"},
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}

_cache = {"data": None, "ts": 0}
_cache_lock = threading.Lock()
_CACHE_TTL = 300  # 5 minutes


# ─── Internal ─────────────────────────────────────────────────────────────────

def _fetch_one(idx):
    """Fetch a single global index from Yahoo Finance v8 chart API."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{idx['symbol']}"
        params = {"interval": "1d", "range": "5d"}
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=8)

        if resp.status_code != 200:
            return None

        data = resp.json()
        meta = data["chart"]["result"][0]["meta"]

        price = float(meta.get("regularMarketPrice", 0))
        prev_close = float(
            meta.get("chartPreviousClose", 0)
            or meta.get("previousClose", 0)
        )

        if not price or not prev_close:
            return None

        change_pct = round((price - prev_close) / prev_close * 100, 2)

        return {
            "name": idx["name"],
            "desc": idx["desc"],
            "flag": idx["flag"],
            "val": round(price),
            "chg": change_pct,
            "live": True,
        }

    except Exception as e:
        log.debug("Yahoo Finance failed for %s: %s", idx["symbol"], e)
        return None


# ─── Public API ───────────────────────────────────────────────────────────────

def fetch_global_indices():
    """
    Fetch global market data from Yahoo Finance.
    All symbols fetched in parallel.

    Returns:
        list of dicts [{name, desc, flag, val, chg, live}, ...] in display order
        None if all fetches failed
    """
    with _cache_lock:
        now = time.time()
        if _cache["data"] and (now - _cache["ts"]) < _CACHE_TTL:
            return _cache["data"]

    results = []

    with ThreadPoolExecutor(max_workers=len(GLOBAL_INDICES)) as pool:
        futures = {pool.submit(_fetch_one, idx): idx for idx in GLOBAL_INDICES}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    if not results:
        log.warning("All global index fetches failed")
        return None

    # Restore display order
    name_order = {idx["name"]: i for i, idx in enumerate(GLOBAL_INDICES)}
    results.sort(key=lambda x: name_order.get(x["name"], 99))

    with _cache_lock:
        _cache["data"] = results
        _cache["ts"] = time.time()
    log.info("Global markets: fetched %d/%d indices", len(results), len(GLOBAL_INDICES))

    return results
