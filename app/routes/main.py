from flask import Blueprint, render_template, request
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
    from app.services.indices_service import fetch_all_indices, get_market_context
    from app.services.market_ai import generate_market_analysis

    idx_data = fetch_all_indices()
    market_ctx = get_market_context()

    # Real AI market analysis (returns None if no API key or error)
    ai_analysis = generate_market_analysis(idx_data, market_ctx["breadth"], market_ctx["fii_dii"])

    return render_template(
        "indices.html",
        idx=idx_data,
        breadth=market_ctx["breadth"],
        fii_dii=market_ctx["fii_dii"],
        is_live=idx_data["live"],
        ai=ai_analysis,
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
