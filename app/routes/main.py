from flask import Blueprint, render_template, request, jsonify
from app.dummy_data import (
    get_all_sectors, get_sector_detail, get_all_stocks_flat, get_stock_by_symbol,
    get_top_gainers, get_top_losers, get_most_active, get_52w_high, get_52w_low,
    get_watchlist, get_screener_results,
    ALL_INDICES, MARKET_BREADTH, FII_DII, SCREENER_PRESETS,
)

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    sectors = get_all_sectors()
    total_stocks = sum(s["stock_count"] for s in sectors)
    total_indices = sum(len(v) for v in ALL_INDICES.values())
    return render_template(
        "index.html",
        sectors=sectors, indices=ALL_INDICES,
        total_stocks=total_stocks, total_indices=total_indices,
        top_gainers=get_top_gainers(6), top_losers=get_top_losers(6),
        most_active=get_most_active(6), w52_high=get_52w_high(6), w52_low=get_52w_low(6),
        breadth=MARKET_BREADTH, fii_dii=FII_DII,
    )


@main_bp.route("/sectors")
def sectors():
    return render_template("sectors.html", sectors=get_all_sectors())


@main_bp.route("/sector/<slug>")
def sector_detail(slug):
    sector = get_sector_detail(slug)
    if not sector:
        return "Sector not found", 404
    return render_template("sector_detail.html", sector=sector)


@main_bp.route("/indices")
def indices():
    from datetime import datetime
    from app.services.indices_service import fetch_all_indices, get_market_context
    from app.services.global_markets import fetch_global_indices
    from app.services.nse_data import is_market_hours
    from app.services.market_ai import generate_market_analysis

    idx_data = fetch_all_indices()
    market_ctx = get_market_context()
    valuation = market_ctx.get("valuation")

    # Global markets (Yahoo Finance — returns None if unavailable)
    global_data = fetch_global_indices()

    # AI Market Intelligence (OpenAI GPT-4.1 mini — cached 5 min)
    ai = None
    if idx_data.get("live"):
        ai = generate_market_analysis(
            idx_data, market_ctx["breadth"], market_ctx["fii_dii"], valuation
        )

    return render_template(
        "indices.html",
        idx=idx_data,
        breadth=market_ctx["breadth"],
        fii_dii=market_ctx["fii_dii"],
        valuation=valuation,
        globals=global_data,
        is_live=idx_data["live"],
        is_market_hours=is_market_hours(),
        ai=ai,
        updated_at=datetime.now().strftime("%H:%M:%S"),
    )


@main_bp.route("/stocks")
def all_stocks():
    stocks = get_all_stocks_flat()
    sort_by = request.args.get("sort", "symbol")
    reverse = request.args.get("order", "asc") == "desc"
    if sort_by in ("symbol", "name", "exchange"):
        stocks.sort(key=lambda s: s.get(sort_by, ""), reverse=reverse)
    elif sort_by in ("price", "change", "change_pct", "volume", "market_cap_cr"):
        stocks.sort(key=lambda s: s.get(sort_by, 0), reverse=reverse)
    return render_template("all_stocks.html", stocks=stocks, sort_by=sort_by, order="desc" if not reverse else "asc")


@main_bp.route("/stock/<symbol>")
def stock_detail(symbol):
    stock = get_stock_by_symbol(symbol.upper())
    if not stock:
        return "Stock not found", 404
    return render_template("stock_detail.html", stock=stock)


@main_bp.route("/watchlist")
def watchlist():
    return render_template("watchlist.html", watchlist=get_watchlist())


@main_bp.route("/news")
def news():
    from app.db import get_articles

    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "all")
    per_page = 20

    page = max(1, page)
    articles, total = get_articles(page=page, per_page=per_page, category=category)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    return render_template(
        "news.html",
        news=articles,
        page=page,
        total_pages=total_pages,
        total=total,
        category=category,
    )


@main_bp.route("/screener")
def screener():
    sectors = get_all_sectors()
    total_stocks = sum(s["stock_count"] for s in sectors)

    # Check if a preset was selected
    preset_idx = request.args.get("preset", type=int)
    filters = {}
    results = None

    if preset_idx is not None and 0 <= preset_idx < len(SCREENER_PRESETS):
        filters = SCREENER_PRESETS[preset_idx]["filters"]
        results = get_screener_results(filters)
    else:
        # Check for custom filters from form
        for key in ("min_market_cap", "max_market_cap", "max_pe", "min_div_yield", "min_change_pct", "min_volume"):
            val = request.args.get(key)
            if val:
                filters[key] = val
        if filters:
            results = get_screener_results(filters)

    return render_template(
        "screener.html",
        presets=SCREENER_PRESETS, filters=filters, results=results,
        total_stocks=total_stocks,
    )


# ─── INDEX DETAIL PAGE ─────────────────────────────────────────────────────

@main_bp.route("/index/<token>")
def index_detail(token):
    from app.services.indices_service import fetch_all_indices, fetch_52w_for_index
    from app.services.nse_data import is_market_hours, fetch_index_constituents

    idx_data = fetch_all_indices()

    # Find this index in the table
    index_info = None
    for idx in idx_data.get("all_table", []):
        if idx["token"] == token:
            index_info = idx
            break

    # Also check VIX
    if not index_info and idx_data.get("vix") and idx_data["vix"].get("token") == token:
        index_info = idx_data["vix"]

    if not index_info:
        return "Index not found", 404

    # Compute 52-week range from historical candles (Angel One returns 0 for indices)
    if not index_info.get("high_52w") or not index_info.get("low_52w"):
        w52 = fetch_52w_for_index(token, index_info.get("exchange", "NSE"))
        if w52:
            index_info["low_52w"] = w52["low"]
            index_info["high_52w"] = w52["high"]

    # Get per-index breadth from NSE if available
    index_breadth = _get_index_breadth(index_info.get("name", ""))

    # Get constituent stocks (top movers + sector breakdown) — NSE indices only
    constituents = None
    if index_info.get("exchange") == "NSE":
        constituents = fetch_index_constituents(index_info.get("name", ""))

    return render_template(
        "index_detail.html",
        index=index_info,
        breadth=index_breadth,
        constituents=constituents,
        is_market_hours=is_market_hours(),
    )


# Angel One symbol → NSE index name mapping for breadth lookup
_NSE_NAME_MAP = {
    "NIFTY": "NIFTY 50",
    "BANKNIFTY": "NIFTY BANK",
    "NIFTY NEXT 50": "NIFTY NEXT 50",
    "NIFTY FIN SERVICE": "NIFTY FINANCIAL SERVICES",
    "NIFTY MID SELECT": "NIFTY MIDCAP SELECT",
}


def _get_index_breadth(index_name):
    """Get advance/decline for a specific index from NSE allIndices data."""
    try:
        from app.services.nse_data import _fetch_all_indices
        data = _fetch_all_indices()
        if not data:
            return None

        # Try direct match, then mapped name
        nse_name = _NSE_NAME_MAP.get(index_name.upper(), index_name).upper()

        for item in data.get("data", []):
            item_name = str(item.get("index", "")).upper()
            if item_name == nse_name or item_name == index_name.upper():
                adv = int(item.get("advances", 0) or 0)
                dec = int(item.get("declines", 0) or 0)
                unch = int(item.get("unchanged", 0) or 0)
                total = adv + dec + unch
                if total == 0:
                    return None
                return {
                    "advances": adv,
                    "declines": dec,
                    "unchanged": unch,
                    "total": total,
                    "adv_pct": round(adv / total * 100, 1),
                    "dec_pct": round(dec / total * 100, 1),
                }
    except Exception:
        pass
    return None


# ─── CHART DATA API ─────────────────────────────────────────────────────────

# Angel One interval mapping: key → (interval_code, max_days)
_INTERVAL_MAP = {
    "1D":  ("ONE_MINUTE",    1),
    "1W":  ("FIVE_MINUTE",   7),
    "1M":  ("FIFTEEN_MINUTE", 30),
    "3M":  ("ONE_HOUR",      90),
    "6M":  ("ONE_DAY",       180),
    "1Y":  ("ONE_DAY",       365),
    "5Y":  ("ONE_DAY",       1825),
}


@main_bp.route("/api/index-history")
def api_index_history():
    """
    JSON API for chart data.
    Params: token, exchange (default NSE), tf (1D/1W/1M/3M/6M/1Y/5Y)
    Returns: {candles: [[timestamp_ms, open, high, low, close], ...]}
    """
    from app.services.indices_service import fetch_index_history

    token = request.args.get("token", "")
    exchange = request.args.get("exchange", "NSE")
    tf = request.args.get("tf", "1M")

    if not token:
        return jsonify({"error": "token required"}), 400

    interval_code, days = _INTERVAL_MAP.get(tf, ("ONE_DAY", 30))
    candles = fetch_index_history(token, exchange, interval_code, days)

    if not candles:
        return jsonify({"candles": []})

    # Format: [[timestamp_ms, O, H, L, C], ...]
    # Angel One returns: [DateTime, O, H, L, C, Volume]
    formatted = []
    for c in candles:
        try:
            from datetime import datetime
            ts = int(datetime.strptime(c[0], "%Y-%m-%dT%H:%M:%S%z").timestamp())
            formatted.append([ts, c[1], c[2], c[3], c[4]])
        except (ValueError, IndexError):
            continue

    return jsonify({"candles": formatted})


@main_bp.route("/api/sector-timeframes")
def api_sector_timeframes():
    """
    JSON API for sector multi-timeframe returns.
    Returns: {token: {"1W": float, "1M": float, "3M": float}, ...}
    Fetched async from frontend so it doesn't block page load.
    """
    from app.services.indices_service import fetch_all_indices, fetch_sector_timeframe_returns

    idx_data = fetch_all_indices()
    sector_perf = idx_data.get("sector_performance", [])

    if not sector_perf:
        return jsonify({})

    returns = fetch_sector_timeframe_returns(sector_perf)
    return jsonify(returns)
