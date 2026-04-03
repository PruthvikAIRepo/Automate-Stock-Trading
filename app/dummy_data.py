"""
Dummy data for Phase 1 UI development.
Based on NSE Industry Classification (12 Macro Sectors → 22 Sectors → 59 Industries).
All prices are fictional for UI development.
"""

import random

random.seed(42)


def _price():
    return round(random.uniform(50, 5000), 2)


def _change():
    return round(random.uniform(-5, 5), 2)


def _pct(change, price):
    if price == 0:
        return 0
    return round((change / (price - change)) * 100, 2)


def _sparkline_points(is_positive):
    """Generate sparkline SVG polyline points."""
    pts = []
    y = 12
    for i in range(10):
        y += random.uniform(-4, 3) if is_positive else random.uniform(-3, 4)
        y = max(2, min(22, y))
        pts.append(f"{i * 7},{y:.1f}")
    return " ".join(pts)


def _sparkline_svg(is_positive):
    color = "#00D09C" if is_positive else "#EF4444"
    pts = _sparkline_points(is_positive)
    return (
        f'<svg width="64" height="24" viewBox="0 0 63 24" fill="none">'
        f'<polyline points="{pts}" stroke="{color}" stroke-width="1.5" fill="none" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


def _fmt_vol(vol):
    if vol >= 10000000:
        return f"{vol / 10000000:.1f}Cr"
    if vol >= 100000:
        return f"{vol / 100000:.1f}L"
    if vol >= 1000:
        return f"{vol / 1000:.1f}K"
    return str(vol)


def _fmt_mcap(mcap):
    if mcap >= 100000:
        return f"₹{mcap / 100000:.1f}L Cr"
    if mcap >= 1000:
        return f"₹{mcap / 1000:.1f}K Cr"
    return f"₹{mcap:.0f} Cr"


def _stock(symbol, name, exchange="NSE", series="EQ"):
    price = _price()
    change = _change()
    volume = random.randint(10000, 50000000)
    mcap = round(random.uniform(100, 500000), 0)
    low52 = round(price * random.uniform(0.5, 0.85), 2)
    high52 = round(price * random.uniform(1.1, 1.6), 2)
    return {
        "symbol": symbol,
        "name": name,
        "exchange": exchange,
        "series": series,
        "price": price,
        "change": change,
        "change_pct": _pct(change, price),
        "open": round(price - random.uniform(-20, 20), 2),
        "high": round(price + random.uniform(0, 30), 2),
        "low": round(price - random.uniform(0, 30), 2),
        "prev_close": round(price - change, 2),
        "volume": volume,
        "volume_fmt": _fmt_vol(volume),
        "market_cap_cr": mcap,
        "market_cap_fmt": _fmt_mcap(mcap),
        "low_52w": low52,
        "high_52w": high52,
        "pct_from_52w_low": round((price - low52) / low52 * 100, 1) if low52 > 0 else 0,
        "pos_in_52w": round((price - low52) / (high52 - low52) * 100, 1) if high52 > low52 else 50,
        "pe_ratio": round(random.uniform(5, 80), 1),
        "pb_ratio": round(random.uniform(0.5, 12), 1),
        "div_yield": round(random.uniform(0, 4), 2),
        "sparkline": _sparkline_svg(change >= 0),
    }


# ─── NSE MACRO SECTORS (12) + Others ─────────────────────────────────────────

SECTORS = {
    "financial-services": {
        "name": "Financial Services",
        "icon": "bi-bank",
        "color": "#3b82f6",
        "description": "Banks, NBFCs, Insurance, Capital Markets",
        "sectors": {
            "Banks": {
                "industries": {
                    "Public Sector Banks": [
                        _stock("SBIN", "State Bank of India"),
                        _stock("BANKBARODA", "Bank of Baroda"),
                        _stock("PNB", "Punjab National Bank"),
                        _stock("CANBK", "Canara Bank"),
                        _stock("UNIONBANK", "Union Bank of India"),
                        _stock("IOB", "Indian Overseas Bank"),
                        _stock("BANKINDIA", "Bank of India"),
                        _stock("INDIANB", "Indian Bank"),
                    ],
                    "Private Sector Banks": [
                        _stock("HDFCBANK", "HDFC Bank Ltd"),
                        _stock("ICICIBANK", "ICICI Bank Ltd"),
                        _stock("KOTAKBANK", "Kotak Mahindra Bank"),
                        _stock("AXISBANK", "Axis Bank Ltd"),
                        _stock("INDUSINDBK", "IndusInd Bank Ltd"),
                        _stock("BANDHANBNK", "Bandhan Bank Ltd"),
                        _stock("FEDERALBNK", "Federal Bank Ltd"),
                        _stock("IDFCFIRSTB", "IDFC First Bank"),
                        _stock("RBLBANK", "RBL Bank Ltd"),
                        _stock("YESBANK", "Yes Bank Ltd"),
                    ],
                },
            },
            "Finance": {
                "industries": {
                    "NBFCs": [
                        _stock("BAJFINANCE", "Bajaj Finance Ltd"),
                        _stock("BAJAJFINSV", "Bajaj Finserv Ltd"),
                        _stock("SHRIRAMFIN", "Shriram Finance Ltd"),
                        _stock("M&MFIN", "Mahindra & Mahindra Fin"),
                        _stock("CHOLAFIN", "Cholamandalam Inv"),
                        _stock("MANAPPURAM", "Manappuram Finance"),
                        _stock("MUTHOOTFIN", "Muthoot Finance Ltd"),
                        _stock("LICHSGFIN", "LIC Housing Finance"),
                        _stock("PEL", "Piramal Enterprises"),
                    ],
                    "Housing Finance": [
                        _stock("CANFINHOME", "Can Fin Homes Ltd"),
                        _stock("AAVAS", "Aavas Financiers Ltd"),
                        _stock("HOMEFIRST", "Home First Finance"),
                    ],
                    "Capital Markets": [
                        _stock("ANGELONE", "Angel One Ltd"),
                        _stock("MOTILALOFS", "Motilal Oswal Fin"),
                        _stock("CDSL", "Central Depository Svc"),
                        _stock("BSE", "BSE Ltd", "BSE"),
                        _stock("CAMS", "Computer Age Mgmt"),
                        _stock("MCX", "Multi Commodity Exch"),
                    ],
                },
            },
            "Insurance": {
                "industries": {
                    "Life Insurance": [
                        _stock("LICI", "Life Insurance Corp"),
                        _stock("SBILIFE", "SBI Life Insurance"),
                        _stock("HDFCLIFE", "HDFC Life Insurance"),
                        _stock("ICICIPRULI", "ICICI Prudential Life"),
                    ],
                    "General Insurance": [
                        _stock("GICRE", "General Insurance Corp"),
                        _stock("NIACL", "New India Assurance"),
                        _stock("STARHEALTH", "Star Health Insurance"),
                    ],
                },
            },
        },
    },
    "information-technology": {
        "name": "Information Technology",
        "icon": "bi-cpu",
        "color": "#06b6d4",
        "description": "IT Services, Software, BPO/KPO",
        "sectors": {
            "IT - Software": {
                "industries": {
                    "IT Services & Consulting": [
                        _stock("TCS", "Tata Consultancy Svc"),
                        _stock("INFY", "Infosys Ltd"),
                        _stock("WIPRO", "Wipro Ltd"),
                        _stock("HCLTECH", "HCL Technologies"),
                        _stock("TECHM", "Tech Mahindra Ltd"),
                        _stock("LTIM", "LTIMindtree Ltd"),
                        _stock("MPHASIS", "Mphasis Ltd"),
                        _stock("COFORGE", "Coforge Ltd"),
                        _stock("PERSISTENT", "Persistent Systems"),
                        _stock("TATAELXSI", "Tata Elxsi Ltd"),
                        _stock("KPITTECH", "KPIT Technologies"),
                    ],
                },
            },
        },
    },
    "consumer-discretionary": {
        "name": "Consumer Discretionary",
        "icon": "bi-cart4",
        "color": "#ec4899",
        "description": "Automobiles, Textiles, Media, Hotels",
        "sectors": {
            "Automobile": {
                "industries": {
                    "Passenger Vehicles": [
                        _stock("MARUTI", "Maruti Suzuki India"),
                        _stock("TATAMOTORS", "Tata Motors Ltd"),
                        _stock("M&M", "Mahindra & Mahindra"),
                        _stock("HEROMOTOCO", "Hero MotoCorp Ltd"),
                        _stock("BAJAJ-AUTO", "Bajaj Auto Ltd"),
                        _stock("EICHERMOT", "Eicher Motors Ltd"),
                        _stock("TVSMOTOR", "TVS Motor Company"),
                    ],
                    "Auto Components": [
                        _stock("MOTHERSON", "Samvardhana Motherson"),
                        _stock("BOSCHLTD", "Bosch Ltd"),
                        _stock("BHARATFORG", "Bharat Forge Ltd"),
                        _stock("MRF", "MRF Ltd"),
                        _stock("APOLLOTYRE", "Apollo Tyres Ltd"),
                        _stock("EXIDEIND", "Exide Industries"),
                    ],
                },
            },
            "Media & Entertainment": {
                "industries": {
                    "Media": [
                        _stock("ZEEL", "Zee Entertainment"),
                        _stock("PVRINOX", "PVR INOX Ltd"),
                        _stock("SUNTV", "Sun TV Network"),
                    ],
                },
            },
        },
    },
    "healthcare": {
        "name": "Healthcare",
        "icon": "bi-heart-pulse",
        "color": "#22c55e",
        "description": "Pharma, Hospitals, Diagnostics",
        "sectors": {
            "Pharmaceuticals": {
                "industries": {
                    "Pharmaceuticals": [
                        _stock("SUNPHARMA", "Sun Pharmaceutical"),
                        _stock("DRREDDY", "Dr. Reddy's Labs"),
                        _stock("CIPLA", "Cipla Ltd"),
                        _stock("DIVISLAB", "Divi's Laboratories"),
                        _stock("LUPIN", "Lupin Ltd"),
                        _stock("AUROPHARMA", "Aurobindo Pharma"),
                        _stock("TORNTPHARM", "Torrent Pharma"),
                        _stock("BIOCON", "Biocon Ltd"),
                        _stock("ALKEM", "Alkem Laboratories"),
                        _stock("IPCALAB", "IPCA Laboratories"),
                        _stock("ABBOTINDIA", "Abbott India Ltd"),
                    ],
                },
            },
            "Healthcare Services": {
                "industries": {
                    "Hospitals": [
                        _stock("APOLLOHOSP", "Apollo Hospitals"),
                        _stock("FORTIS", "Fortis Healthcare"),
                        _stock("MAXHEALTH", "Max Healthcare"),
                        _stock("NH", "Narayana Hrudayalaya"),
                    ],
                },
            },
        },
    },
    "industrials": {
        "name": "Industrials",
        "icon": "bi-gear",
        "color": "#f59e0b",
        "description": "Capital Goods, Construction, Defence",
        "sectors": {
            "Capital Goods": {
                "industries": {
                    "Electrical Equipment": [
                        _stock("SIEMENS", "Siemens Ltd"),
                        _stock("ABB", "ABB India Ltd"),
                        _stock("HAVELLS", "Havells India Ltd"),
                        _stock("POLYCAB", "Polycab India Ltd"),
                        _stock("BHEL", "Bharat Heavy Elec"),
                        _stock("CROMPTON", "Crompton Greaves CE"),
                    ],
                    "Defence & Machinery": [
                        _stock("LT", "Larsen & Toubro Ltd"),
                        _stock("BEL", "Bharat Electronics"),
                        _stock("HAL", "Hindustan Aeronautics"),
                        _stock("COCHINSHIP", "Cochin Shipyard Ltd"),
                    ],
                },
            },
            "Construction": {
                "industries": {
                    "Cement": [
                        _stock("ULTRACEMCO", "UltraTech Cement"),
                        _stock("SHREECEM", "Shree Cement Ltd"),
                        _stock("AMBUJACEM", "Ambuja Cements"),
                        _stock("ACC", "ACC Ltd"),
                        _stock("DALMIACEM", "Dalmia Bharat Ltd"),
                    ],
                },
            },
        },
    },
    "energy": {
        "name": "Energy",
        "icon": "bi-lightning-charge",
        "color": "#ef4444",
        "description": "Oil & Gas, Refineries, Gas Distribution",
        "sectors": {
            "Oil Gas & Fuels": {
                "industries": {
                    "Oil & Gas": [
                        _stock("RELIANCE", "Reliance Industries"),
                        _stock("ONGC", "Oil & Natural Gas"),
                        _stock("BPCL", "Bharat Petroleum"),
                        _stock("IOC", "Indian Oil Corp"),
                        _stock("HINDPETRO", "Hindustan Petroleum"),
                        _stock("GAIL", "GAIL India Ltd"),
                        _stock("IGL", "Indraprastha Gas"),
                        _stock("PETRONET", "Petronet LNG Ltd"),
                    ],
                },
            },
        },
    },
    "fmcg": {
        "name": "FMCG",
        "icon": "bi-basket3",
        "color": "#a855f7",
        "description": "Food, Beverages, Personal Care",
        "sectors": {
            "FMCG": {
                "industries": {
                    "Food & Beverages": [
                        _stock("NESTLEIND", "Nestle India Ltd"),
                        _stock("BRITANNIA", "Britannia Industries"),
                        _stock("TATACONSUM", "Tata Consumer Prod"),
                        _stock("MARICO", "Marico Ltd"),
                        _stock("DABUR", "Dabur India Ltd"),
                        _stock("ITC", "ITC Ltd"),
                        _stock("HINDUNILVR", "Hindustan Unilever"),
                        _stock("COLPAL", "Colgate-Palmolive"),
                        _stock("PIDILITIND", "Pidilite Industries"),
                        _stock("VBL", "Varun Beverages Ltd"),
                    ],
                },
            },
        },
    },
    "commodities": {
        "name": "Commodities",
        "icon": "bi-gem",
        "color": "#78716c",
        "description": "Metals, Mining, Chemicals",
        "sectors": {
            "Metals & Mining": {
                "industries": {
                    "Steel & Metals": [
                        _stock("TATASTEEL", "Tata Steel Ltd"),
                        _stock("JSWSTEEL", "JSW Steel Ltd"),
                        _stock("HINDALCO", "Hindalco Industries"),
                        _stock("VEDL", "Vedanta Ltd"),
                        _stock("NMDC", "NMDC Ltd"),
                        _stock("SAIL", "Steel Authority India"),
                    ],
                },
            },
            "Chemicals": {
                "industries": {
                    "Specialty Chemicals": [
                        _stock("PIIND", "PI Industries Ltd"),
                        _stock("SRF", "SRF Ltd"),
                        _stock("UPL", "UPL Ltd"),
                        _stock("DEEPAKNITRI", "Deepak Nitrite"),
                    ],
                },
            },
        },
    },
    "services": {
        "name": "Services",
        "icon": "bi-building",
        "color": "#64748b",
        "description": "Retail, Logistics, Real Estate",
        "sectors": {
            "Retail & Logistics": {
                "industries": {
                    "Retail & E-Commerce": [
                        _stock("DMART", "Avenue Supermarts"),
                        _stock("TITAN", "Titan Company Ltd"),
                        _stock("ZOMATO", "Zomato Ltd"),
                        _stock("NYKAA", "FSN E-Commerce"),
                        _stock("PAYTM", "One97 Communications"),
                    ],
                    "Logistics": [
                        _stock("ADANIPORTS", "Adani Ports & SEZ"),
                        _stock("INDIGO", "InterGlobe Aviation"),
                        _stock("DELHIVERY", "Delhivery Ltd"),
                    ],
                    "Real Estate": [
                        _stock("DLF", "DLF Ltd"),
                        _stock("GODREJPROP", "Godrej Properties"),
                        _stock("OBEROIRLTY", "Oberoi Realty Ltd"),
                        _stock("LODHA", "Macrotech Developers"),
                    ],
                },
            },
        },
    },
    "telecom": {
        "name": "Telecommunication",
        "icon": "bi-broadcast",
        "color": "#0ea5e9",
        "description": "Telecom Services & Infrastructure",
        "sectors": {
            "Telecom": {
                "industries": {
                    "Telecom Services": [
                        _stock("BHARTIARTL", "Bharti Airtel Ltd"),
                        _stock("IDEA", "Vodafone Idea Ltd"),
                        _stock("TATACOMM", "Tata Communications"),
                        _stock("INDUSTOWER", "Indus Towers Ltd"),
                    ],
                },
            },
        },
    },
    "utilities": {
        "name": "Utilities",
        "icon": "bi-plug",
        "color": "#f97316",
        "description": "Power Generation & Distribution",
        "sectors": {
            "Power": {
                "industries": {
                    "Power": [
                        _stock("NTPC", "NTPC Ltd"),
                        _stock("POWERGRID", "Power Grid Corp"),
                        _stock("TATAPOWER", "Tata Power Company"),
                        _stock("ADANIGREEN", "Adani Green Energy"),
                        _stock("NHPC", "NHPC Ltd"),
                        _stock("SUZLON", "Suzlon Energy Ltd"),
                        _stock("IREDA", "Indian Renewable Energy"),
                    ],
                },
            },
        },
    },
    "others": {
        "name": "Others",
        "icon": "bi-three-dots",
        "color": "#6b7280",
        "description": "Conglomerates & Uncategorized",
        "sectors": {
            "Others": {
                "industries": {
                    "Others": [
                        _stock("ADANIENT", "Adani Enterprises"),
                        _stock("IRCTC", "Indian Railway Catering"),
                        _stock("RECLTD", "REC Ltd"),
                        _stock("PFC", "Power Finance Corp"),
                    ],
                },
            },
        },
    },
}


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def get_all_sectors():
    result = []
    for slug, sector in SECTORS.items():
        stock_count = 0
        industry_count = 0
        for sec_data in sector["sectors"].values():
            for ind_name, stocks in sec_data["industries"].items():
                industry_count += 1
                stock_count += len(stocks)
        top_stocks = []
        for sec_data in sector["sectors"].values():
            for stocks in sec_data["industries"].values():
                top_stocks.extend(stocks[:3])
                if len(top_stocks) >= 5:
                    break
            if len(top_stocks) >= 5:
                break
        # Sector average change
        all_pcts = []
        for sec_data in sector["sectors"].values():
            for stocks in sec_data["industries"].values():
                all_pcts.extend(s["change_pct"] for s in stocks)
        avg_change = round(sum(all_pcts) / len(all_pcts), 2) if all_pcts else 0

        result.append({
            "slug": slug,
            "name": sector["name"],
            "icon": sector["icon"],
            "color": sector["color"],
            "description": sector["description"],
            "stock_count": stock_count,
            "industry_count": industry_count,
            "top_stocks": top_stocks[:5],
            "avg_change": avg_change,
        })
    return result


def get_sector_detail(slug):
    sector = SECTORS.get(slug)
    if not sector:
        return None
    return {
        "slug": slug, "name": sector["name"], "icon": sector["icon"],
        "color": sector["color"], "description": sector["description"],
        "sectors": sector["sectors"],
    }


def get_all_stocks_flat():
    all_stocks = []
    for sector in SECTORS.values():
        for sec_data in sector["sectors"].values():
            for stocks in sec_data["industries"].values():
                all_stocks.extend(stocks)
    return all_stocks


def get_stock_by_symbol(symbol):
    for sector in SECTORS.values():
        for sec_data in sector["sectors"].values():
            for stocks in sec_data["industries"].values():
                for s in stocks:
                    if s["symbol"] == symbol:
                        return s
    return None


def get_top_gainers(n=10):
    return sorted(get_all_stocks_flat(), key=lambda s: s["change_pct"], reverse=True)[:n]


def get_top_losers(n=10):
    return sorted(get_all_stocks_flat(), key=lambda s: s["change_pct"])[:n]


def get_most_active(n=10):
    return sorted(get_all_stocks_flat(), key=lambda s: s["volume"], reverse=True)[:n]


def get_52w_high(n=10):
    return sorted(get_all_stocks_flat(), key=lambda s: s["pos_in_52w"], reverse=True)[:n]


def get_52w_low(n=10):
    return sorted(get_all_stocks_flat(), key=lambda s: s["pos_in_52w"])[:n]


# ─── MARKET INDICES ───────────────────────────────────────────────────────────

def _index(name, value, exchange="NSE"):
    change = round(random.uniform(-300, 300), 2)
    pct = round((change / (value - change)) * 100, 2)
    return {
        "name": name, "value": value, "change": change,
        "change_pct": pct, "exchange": exchange,
        "sparkline": _sparkline_svg(change >= 0),
    }


BROAD_MARKET_INDICES = [
    _index("NIFTY 50", 24856.50), _index("NIFTY NEXT 50", 62340.80),
    _index("NIFTY 100", 25010.25), _index("NIFTY 200", 13120.45),
    _index("NIFTY 500", 22580.30), _index("NIFTY MIDCAP 50", 15632.10),
    _index("NIFTY MIDCAP 100", 56240.65), _index("NIFTY SMLCAP 50", 8234.90),
    _index("NIFTY SMLCAP 100", 18650.40), _index("NIFTY SMLCAP 250", 17280.55),
    _index("SENSEX", 81840.75, "BSE"), _index("BSE MIDCAP", 41250.30, "BSE"),
    _index("BSE SMALLCAP", 48320.60, "BSE"), _index("BSE 100", 26140.45, "BSE"),
    _index("BSE 200", 11560.80, "BSE"), _index("BSE 500", 38720.15, "BSE"),
]

SECTORAL_INDICES = [
    _index("NIFTY BANK", 51240.30), _index("NIFTY FIN SVC", 22350.60),
    _index("NIFTY PVT BANK", 24560.80), _index("NIFTY PSU BANK", 7125.45),
    _index("NIFTY IT", 38450.20), _index("NIFTY AUTO", 25680.90),
    _index("NIFTY PHARMA", 20340.55), _index("NIFTY FMCG", 56780.65),
    _index("NIFTY METAL", 9120.40), _index("NIFTY ENERGY", 38920.80),
    _index("NIFTY REALTY", 1025.60), _index("NIFTY MEDIA", 2156.35),
    _index("BSE BANKEX", 59420.30, "BSE"), _index("BSE AUTO", 48250.60, "BSE"),
    _index("BSE IT", 42130.80, "BSE"), _index("BSE HEALTHCARE", 38450.25, "BSE"),
    _index("BSE METAL", 31240.70, "BSE"), _index("BSE POWER", 8450.30, "BSE"),
]

THEMATIC_INDICES = [
    _index("NIFTY ALPHA 50", 48230.80), _index("NIFTY MOMENTUM 30", 24560.70),
    _index("NIFTY100 QUALITY 30", 5680.45), _index("NIFTY50 VALUE 20", 13240.80),
    _index("NIFTY LOW VOL 50", 20340.90), _index("NIFTY100 ESG", 4120.60),
    _index("NIFTY EV & AUTO", 3250.90), _index("NIFTY CONSUMPTION", 12450.70),
    _index("NIFTY INDIA DEFENCE", 6250.80), _index("NIFTY INDIA MFG", 12340.65),
    _index("BSE IPO INDEX", 18720.30, "BSE"), _index("BSE GREENEX", 4230.60, "BSE"),
    _index("BSE MOMENTUM", 2456.70, "BSE"), _index("BSE QUALITY", 3210.45, "BSE"),
]

ALL_INDICES = {
    "broad_market": BROAD_MARKET_INDICES,
    "sectoral": SECTORAL_INDICES,
    "thematic": THEMATIC_INDICES,
}

# ─── MARKET BREADTH ───────────────────────────────────────────────────────────
MARKET_BREADTH = {
    "advances": random.randint(800, 1400),
    "declines": random.randint(600, 1200),
    "unchanged": random.randint(50, 200),
}
MARKET_BREADTH["total"] = MARKET_BREADTH["advances"] + MARKET_BREADTH["declines"] + MARKET_BREADTH["unchanged"]
MARKET_BREADTH["adv_pct"] = round(MARKET_BREADTH["advances"] / MARKET_BREADTH["total"] * 100, 1)
MARKET_BREADTH["dec_pct"] = round(MARKET_BREADTH["declines"] / MARKET_BREADTH["total"] * 100, 1)
MARKET_BREADTH["unch_pct"] = round(MARKET_BREADTH["unchanged"] / MARKET_BREADTH["total"] * 100, 1)

FII_DII = {
    "fii_buy": round(random.uniform(5000, 15000), 2),
    "fii_sell": round(random.uniform(5000, 15000), 2),
    "dii_buy": round(random.uniform(5000, 15000), 2),
    "dii_sell": round(random.uniform(5000, 15000), 2),
}
FII_DII["fii_net"] = round(FII_DII["fii_buy"] - FII_DII["fii_sell"], 2)
FII_DII["dii_net"] = round(FII_DII["dii_buy"] - FII_DII["dii_sell"], 2)


# ─── WATCHLIST ────────────────────────────────────────────────────────────────

def get_watchlist():
    symbols_alerts = [
        ("RELIANCE", "Target ₹3,200 hit"),
        ("TCS", "Near 52W High"),
        ("HDFCBANK", ""),
        ("INFY", "Below ₹1,800 support"),
        ("SBIN", ""),
        ("TATAMOTORS", "Breakout above ₹650"),
        ("BAJFINANCE", ""),
        ("ITC", "Dividend ex-date Apr 5"),
        ("WIPRO", ""),
        ("ADANIENT", "High volatility alert"),
    ]
    added_dates = [
        "28 Mar 2026", "25 Mar 2026", "20 Mar 2026", "18 Mar 2026",
        "15 Mar 2026", "12 Mar 2026", "10 Mar 2026", "8 Mar 2026",
        "5 Mar 2026", "1 Mar 2026",
    ]
    result = []
    for i, (sym, alert) in enumerate(symbols_alerts):
        stock = get_stock_by_symbol(sym)
        if stock:
            entry = dict(stock)
            entry["alert"] = alert
            entry["added_date"] = added_dates[i]
            result.append(entry)
    return result


# ─── NEWS ─────────────────────────────────────────────────────────────────────

# ─── SCREENER ─────────────────────────────────────────────────────────────────

SCREENER_PRESETS = [
    {
        "name": "Large Cap Leaders",
        "description": "Market cap > ₹50K Cr",
        "icon": "bi-trophy",
        "filters": {"min_market_cap": 50000},
    },
    {
        "name": "High Dividend",
        "description": "Div yield > 2%",
        "icon": "bi-cash-stack",
        "filters": {"min_div_yield": 2},
    },
    {
        "name": "Low PE Value",
        "description": "P/E ratio < 20",
        "icon": "bi-tag",
        "filters": {"max_pe": 20},
    },
    {
        "name": "52W High Zone",
        "description": "Near 52-week highs",
        "icon": "bi-arrow-up-circle",
        "filters": {"min_pos_52w": 85},
    },
    {
        "name": "High Volume",
        "description": "Volume > 1 Cr",
        "icon": "bi-bar-chart-line",
        "filters": {"min_volume": 10000000},
    },
    {
        "name": "Mid Cap Growth",
        "description": "₹5K-50K Cr market cap",
        "icon": "bi-graph-up-arrow",
        "filters": {"min_market_cap": 5000, "max_market_cap": 50000},
    },
    {
        "name": "Small Cap Gems",
        "description": "Market cap < ₹5K Cr",
        "icon": "bi-gem",
        "filters": {"max_market_cap": 5000},
    },
    {
        "name": "Momentum Plays",
        "description": "Change > +2% today",
        "icon": "bi-rocket-takeoff",
        "filters": {"min_change_pct": 2},
    },
]


def get_screener_results(filters):
    """Filter stocks based on criteria. Returns matching stocks."""
    stocks = get_all_stocks_flat()
    results = []
    for s in stocks:
        match = True
        if filters.get("min_market_cap") and s["market_cap_cr"] < float(filters["min_market_cap"]):
            match = False
        if filters.get("max_market_cap") and s["market_cap_cr"] > float(filters["max_market_cap"]):
            match = False
        if filters.get("min_pe") and s["pe_ratio"] < float(filters["min_pe"]):
            match = False
        if filters.get("max_pe") and s["pe_ratio"] > float(filters["max_pe"]):
            match = False
        if filters.get("min_div_yield") and s["div_yield"] < float(filters["min_div_yield"]):
            match = False
        if filters.get("min_change_pct") and s["change_pct"] < float(filters["min_change_pct"]):
            match = False
        if filters.get("min_volume") and s["volume"] < float(filters["min_volume"]):
            match = False
        if filters.get("min_pos_52w") and s["pos_in_52w"] < float(filters["min_pos_52w"]):
            match = False
        if match:
            results.append(s)
    return sorted(results, key=lambda x: x["market_cap_cr"], reverse=True)
