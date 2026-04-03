"""
Real-time Market Data Service — Angel One SmartWebSocketV2 + Flask-SocketIO.

Architecture:
  Angel One WebSocket → realtime.py (background thread) → Flask-SocketIO → Browser

Handles:
- WebSocket connection to Angel One for real-time index ticks
- Broadcasts LTP/change updates to all connected browsers via Socket.IO
- Auto-reconnect on disconnect
- Only active during market hours (9:00-15:45 IST)
- Subscribes to hero indices (NIFTY 50, BANK NIFTY) + VIX + top sectoral

Rate: Angel One allows 1000 tokens/connection, 3 connections max.
We use 1 connection for ~20 key indices (LTP mode = minimal bandwidth).
"""

import json
import logging
import threading
import time

log = logging.getLogger(__name__)

# State
_ws_thread = None
_socketio = None
_running = False

# Key indices to stream (token, exchange_type, name)
# Exchange types: NSE_CM=1, BSE_CM=3, MCX_FO=5
STREAM_TOKENS = [
    # NSE Broad
    {"token": "99926000", "exchange": 1, "name": "NIFTY"},         # Nifty 50
    {"token": "99926009", "exchange": 1, "name": "BANKNIFTY"},     # Bank Nifty
    {"token": "99926017", "exchange": 1, "name": "INDIA VIX"},     # VIX
    {"token": "99926013", "exchange": 1, "name": "NIFTY NEXT 50"},
    {"token": "99926004", "exchange": 1, "name": "NIFTY 500"},
    {"token": "99926011", "exchange": 1, "name": "NIFTY MIDCAP 100"},
    {"token": "99926032", "exchange": 1, "name": "NIFTY SMLCAP 100"},
    # NSE Sectoral
    {"token": "99926008", "exchange": 1, "name": "NIFTY IT"},
    {"token": "99926037", "exchange": 1, "name": "NIFTY FIN SERVICE"},
    {"token": "99926023", "exchange": 1, "name": "NIFTY PHARMA"},
    {"token": "99926029", "exchange": 1, "name": "NIFTY AUTO"},
    {"token": "99926020", "exchange": 1, "name": "NIFTY ENERGY"},
    {"token": "99926021", "exchange": 1, "name": "NIFTY FMCG"},
    {"token": "99926030", "exchange": 1, "name": "NIFTY METAL"},
    {"token": "99926025", "exchange": 1, "name": "NIFTY PSU BANK"},
    {"token": "99926018", "exchange": 1, "name": "NIFTY REALTY"},
    # BSE
    {"token": "99919000", "exchange": 3, "name": "SENSEX"},
]

# Last known prices (for change calculation)
_last_prices = {}


def init_realtime(socketio):
    """Initialize the real-time service with a Flask-SocketIO instance."""
    global _socketio
    _socketio = socketio
    log.info("Real-time service initialized with SocketIO")


def start_stream():
    """Start the WebSocket stream in a background thread."""
    global _ws_thread, _running

    if _running:
        return

    from app.services.nse_data import is_market_hours
    if not is_market_hours():
        log.info("Market closed — skipping WebSocket stream")
        return

    _running = True
    _ws_thread = threading.Thread(target=_ws_worker, daemon=True)
    _ws_thread.start()
    log.info("Real-time WebSocket stream started")


def stop_stream():
    """Stop the WebSocket stream."""
    global _running
    _running = False
    log.info("Real-time WebSocket stream stopped")


def _ws_worker():
    """Background worker that connects to Angel One WebSocket and relays ticks."""
    global _running

    try:
        from app.services.angel_auth import get_angel_auth
        auth = get_angel_auth()

        if not auth.ensure_session():
            log.error("Cannot start WebSocket — Angel One auth failed")
            _running = False
            return

        from SmartApi.smartWebSocketV2 import SmartWebSocketV2

        sws = SmartWebSocketV2(
            auth.auth_token,
            auth.api_key,
            auth.client_id,
            auth.feed_token,
        )

        # Build token list for subscription
        # Format: [exchange_type, token]
        token_list = [
            [t["exchange"], t["token"]] for t in STREAM_TOKENS
        ]

        # Correlation ID
        correlation_id = "stockpulse_idx"

        def on_data(wsapp, message):
            """Handle incoming tick data."""
            if not _socketio:
                return

            try:
                token = str(message.get("token", ""))
                ltp = message.get("last_traded_price", 0)
                close = message.get("close_price", 0)

                if not token or not ltp:
                    return

                # Angel One sends prices * 100 for some instruments
                # For indices, ltp is in paisa — divide by 100
                ltp = ltp / 100.0
                close = close / 100.0 if close else 0

                change = ltp - close if close else 0
                change_pct = round((change / close) * 100, 2) if close else 0

                tick = {
                    "token": token,
                    "ltp": round(ltp, 2),
                    "change": round(change, 2),
                    "change_pct": change_pct,
                }

                _last_prices[token] = tick

                # Broadcast to all connected browsers
                _socketio.emit("tick", tick, namespace="/live")

            except Exception as e:
                log.debug("Tick parse error: %s", e)

        def on_open(wsapp):
            log.info("Angel One WebSocket connected — subscribing to %d tokens", len(token_list))
            # Mode 1 = LTP (least data, fastest)
            sws.subscribe(correlation_id, 1, token_list)

        def on_error(wsapp, error):
            log.error("WebSocket error: %s", error)

        def on_close(wsapp):
            log.info("WebSocket closed")
            # Auto-reconnect after 5 seconds if still running
            if _running:
                time.sleep(5)
                try:
                    sws.connect()
                except Exception:
                    pass

        sws.on_data = on_data
        sws.on_open = on_open
        sws.on_error = on_error
        sws.on_close = on_close

        sws.connect()

    except Exception as e:
        log.error("WebSocket worker error: %s", e)
        _running = False


def get_latest_prices():
    """Get the latest cached prices from WebSocket stream."""
    return dict(_last_prices)
