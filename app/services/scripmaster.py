"""
ScripMaster Service — Downloads and parses Angel One instrument master.

Downloads the full instrument list (~200K instruments) from Angel One,
filters for indices (instrumenttype == "AMXIDX"), and categorizes them
into Broad Market / Sectoral / Thematic groups.

The ScripMaster JSON is public — no auth needed.
URL: https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json
"""

import json
import logging
import os
import time

import requests

log = logging.getLogger(__name__)

SCRIPMASTER_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
)

# Cache file — so we don't re-download 80MB every restart
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "instance")
CACHE_FILE = os.path.join(CACHE_DIR, "index_tokens.json")
CACHE_MAX_AGE = 86400  # Re-download once per day (24 hours)

# ─── INDEX CATEGORIZATION ────────────────────────────────────────────────────
# Based on NSE/BSE official classification + our research
# These keyword patterns determine which category an index belongs to

BROAD_MARKET_KEYWORDS = [
    "NIFTY 50", "NIFTY NEXT 50", "NIFTY 100", "NIFTY 200", "NIFTY 500",
    "NIFTY MIDCAP", "NIFTY SMLCAP", "NIFTY SMALLCAP", "NIFTY LARGEMIDCAP",
    "SENSEX", "BSE100", "BSE200", "BSE500", "BSE MIDCAP", "BSE SMALLCAP",
    "BSE LARGECAP", "BSE MIDCAP SELECT", "BSE SMALLCAP SELECT",
    "DOL30", "DOL100", "DOL200",  # BSE Dollex indices
    "NIFTY TOTAL", "NIFTY MICROCAP",
]

SECTORAL_KEYWORDS = [
    "BANK", "NIFTY IT", "BSE IT", "AUTO", "PHARMA", "FMCG", "METAL",
    "ENERGY", "REALTY", "MEDIA", "INFRA", "FIN", "PVT BANK", "PSU BANK",
    "SERV SECTOR", "MNC", "PSE", "HEALTHCARE", "BSE HC", "BSE CG",
    "BSE CD", "TECK", "BANKEX", "OILGAS", "BSE POWER", "BSE CPSE",
    "NIFTY COMMODITIES", "NIFTY CONSUMPTION",
    # MCX commodity indices
    "MCXCRUDEX", "MCXCOPRDEX", "MCXSILVDEX", "MCXGOLDEX",
    "MCXMETLDEX", "MCXBULLDEX", "MCXCOMPDEX",
]

# Hero indices — displayed prominently at the top
HERO_TOKENS = {
    "99926000": "NIFTY 50",
    "99926009": "BANK NIFTY",
}

# VIX token — for the fear gauge
VIX_TOKEN = "99926017"

# Key sectoral indices for the sector performance table
SECTORAL_INDEX_TOKENS = {
    "99926009": "NIFTY BANK",
    "99926037": "NIFTY FIN SERVICE",
    "99926008": "NIFTY IT",
    "99926029": "NIFTY AUTO",
    "99926023": "NIFTY PHARMA",
    "99926021": "NIFTY FMCG",
    "99926020": "NIFTY ENERGY",
    "99926018": "NIFTY REALTY",
    "99926025": "NIFTY PSU BANK",
    "99926019": "NIFTY INFRA",
}


def _categorize_index(symbol, name):
    """Determine if an index is broad_market, sectoral, or thematic."""
    check = f"{symbol} {name}".upper()

    for kw in BROAD_MARKET_KEYWORDS:
        if kw.upper() in check:
            return "broad_market"

    for kw in SECTORAL_KEYWORDS:
        if kw.upper() in check:
            return "sectoral"

    return "thematic"


def _exchange_from_token(token):
    """Determine exchange from token prefix."""
    if token.startswith("99926"):
        return "NSE"
    elif token.startswith("99919"):
        return "BSE"
    elif token.startswith("99920"):
        return "MCX"
    return "NSE"


def download_index_tokens(force=False):
    """
    Download ScripMaster and extract all index instruments.

    Returns:
        dict with keys:
            all: [{token, symbol, name, exchange, category}, ...]
            broad_market: [...]
            sectoral: [...]
            thematic: [...]
            hero: [{token, symbol, name, exchange}, ...]
            vix: {token, symbol, name, exchange} or None
            sector_tokens: {token: name, ...}
            by_token: {token: {symbol, name, exchange, category}, ...}
    """
    # Check cache first
    if not force and os.path.exists(CACHE_FILE):
        cache_age = time.time() - os.path.getmtime(CACHE_FILE)
        if cache_age < CACHE_MAX_AGE:
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                log.info(
                    "Loaded %d index tokens from cache (age: %d min)",
                    len(cached.get("all", [])), int(cache_age / 60),
                )
                return cached
            except (json.JSONDecodeError, KeyError):
                log.warning("Cache corrupted, re-downloading")

    log.info("Downloading ScripMaster from Angel One (~80MB)...")

    try:
        resp = requests.get(SCRIPMASTER_URL, timeout=120)
        resp.raise_for_status()
        instruments = resp.json()
    except requests.RequestException as e:
        log.error("ScripMaster download failed: %s", e)
        # Try to return stale cache if available
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return _empty_result()

    # Filter for indices only — strict instrumenttype check
    indices = []
    for inst in instruments:
        if inst.get("instrumenttype") != "AMXIDX":
            continue

        token = str(inst.get("token", ""))
        symbol = inst.get("symbol", inst.get("name", ""))
        name = inst.get("name", symbol)
        exchange = inst.get("exch_seg", _exchange_from_token(token))
        category = _categorize_index(symbol, name)

        indices.append({
            "token": token,
            "symbol": symbol,
            "name": name,
            "exchange": exchange,
            "category": category,
        })

    log.info("Found %d index instruments from ScripMaster", len(indices))

    # Build categorized result
    result = {
        "all": indices,
        "broad_market": [i for i in indices if i["category"] == "broad_market"],
        "sectoral": [i for i in indices if i["category"] == "sectoral"],
        "thematic": [i for i in indices if i["category"] == "thematic"],
        "hero": [i for i in indices if i["token"] in HERO_TOKENS],
        "vix": next((i for i in indices if i["token"] == VIX_TOKEN), None),
        "sector_tokens": SECTORAL_INDEX_TOKENS,
        "by_token": {i["token"]: i for i in indices},
    }

    # Cache to disk
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        log.info("Cached %d index tokens to %s", len(indices), CACHE_FILE)
    except OSError as e:
        log.warning("Failed to cache index tokens: %s", e)

    return result


def _empty_result():
    """Return empty structure when no data available."""
    return {
        "all": [], "broad_market": [], "sectoral": [], "thematic": [],
        "hero": [], "vix": None, "sector_tokens": SECTORAL_INDEX_TOKENS,
        "by_token": {},
    }


def get_index_tokens():
    """
    Get index tokens — from cache if fresh, else download.
    This is the main entry point for other services.
    """
    return download_index_tokens(force=False)
