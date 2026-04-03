"""
Angel One SmartAPI Authentication Service.

Handles:
- Login with API key + client ID + MPIN + auto-generated TOTP
- Session (JWT token) management
- Feed token for WebSocket
- Auto re-login on token expiry
- Thread-safe singleton pattern
"""

import base64
import logging
import os
import threading
import time

import pyotp

log = logging.getLogger(__name__)

# Lazy-loaded SmartConnect — avoids import error if package not installed yet
_SmartConnect = None


def _get_smart_connect_class():
    global _SmartConnect
    if _SmartConnect is None:
        from SmartApi import SmartConnect
        _SmartConnect = SmartConnect
    return _SmartConnect


class AngelAuth:
    """Singleton auth manager for Angel One SmartAPI."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.api_key = os.environ.get("ANGEL_API_KEY", "")
        self.client_id = os.environ.get("ANGEL_CLIENT_ID", "")
        self.mpin = os.environ.get("ANGEL_MPIN", "")
        self.totp_secret = os.environ.get("ANGEL_TOTP_SECRET", "")

        self.smart_api = None
        self.auth_token = None
        self.refresh_token = None
        self.feed_token = None
        self.logged_in = False
        self._login_time = 0

    @property
    def is_configured(self):
        """Check if all required credentials are present."""
        return all([self.api_key, self.client_id, self.mpin, self.totp_secret])

    def login(self):
        """
        Authenticate with Angel One SmartAPI.

        Flow:
        1. Generate TOTP from secret (same as Google Authenticator)
        2. Call generateSession(client_id, mpin, totp)
        3. Store JWT auth token + refresh token + feed token
        """
        if not self.is_configured:
            log.warning("Angel One credentials not configured — skipping login")
            return False

        try:
            SmartConnect = _get_smart_connect_class()
            self.smart_api = SmartConnect(api_key=self.api_key)

            # Generate TOTP code (6-digit, changes every 30 seconds)
            # Angel One provides TOTP secret in hex/UUID format — convert to base32
            secret = self.totp_secret.replace("-", "")
            try:
                secret_bytes = bytes.fromhex(secret)
                b32_secret = base64.b32encode(secret_bytes).decode("utf-8")
            except ValueError:
                # Already base32 or plain text — use as-is
                b32_secret = self.totp_secret
            totp = pyotp.TOTP(b32_secret).now()

            # Login
            data = self.smart_api.generateSession(
                self.client_id, self.mpin, totp
            )

            if not data or not data.get("status"):
                msg = data.get("message", "Unknown error") if data else "No response"
                log.error("Angel One login failed: %s", msg)
                self.logged_in = False
                return False

            self.auth_token = data["data"]["jwtToken"]
            self.refresh_token = data["data"]["refreshToken"]
            self.feed_token = self.smart_api.getfeedToken()
            self.logged_in = True
            self._login_time = time.time()

            log.info(
                "Angel One login successful — client: %s, feed_token: %s...",
                self.client_id, (self.feed_token or "")[:10]
            )
            return True

        except Exception as e:
            log.error("Angel One login error: %s", e)
            self.logged_in = False
            return False

    def ensure_session(self):
        """
        Ensure we have a valid session. Re-login if needed.
        Angel One tokens expire after ~24 hours.
        We re-login if token is older than 20 hours to be safe.
        """
        if not self.is_configured:
            return False

        # Re-login if token is older than 20 hours
        token_age = time.time() - self._login_time
        if not self.logged_in or token_age > 72000:  # 20 hours
            return self.login()

        return True

    def get_market_data(self, mode, exchange_tokens):
        """
        Fetch market data for indices/stocks.

        Args:
            mode: "LTP", "OHLC", or "FULL"
            exchange_tokens: dict like {"NSE": ["99926000", "99926009"], "BSE": ["99919000"]}

        Returns:
            API response data or None on failure

        FULL mode returns per instrument:
            exchange, tradingSymbol, symbolToken, ltp, open, high, low, close,
            lastTradeQty, exchFeedTime, exchTradeTime, netChange, percentChange,
            avgPrice, tradeVolume, opnInterest, lowerCircuit, upperCircuit,
            totBuyQuan, totSellQuan, 52WeekLow, 52WeekHigh, depth
        """
        if not self.ensure_session():
            return None

        try:
            data = self.smart_api.getMarketData(mode, exchange_tokens)
            if data and data.get("status"):
                return data.get("data", {}).get("fetched", [])
            else:
                msg = data.get("message", "Unknown") if data else "No response"
                log.error("getMarketData failed: %s", msg)
                return None
        except Exception as e:
            log.error("getMarketData error: %s", e)
            return None

    def get_candle_data(self, params):
        """
        Fetch historical OHLCV candle data.

        Args:
            params: dict with keys:
                exchange: "NSE" or "BSE"
                symboltoken: "99926000"
                interval: "ONE_MINUTE"|"FIVE_MINUTE"|"FIFTEEN_MINUTE"|
                          "THIRTY_MINUTE"|"ONE_HOUR"|"ONE_DAY"
                fromdate: "2025-01-01 09:15"
                todate: "2025-12-31 15:30"

        Returns:
            List of [datetime, open, high, low, close, volume] arrays or None
        """
        if not self.ensure_session():
            return None

        try:
            data = self.smart_api.getCandleData(params)
            if data and data.get("status"):
                return data.get("data", [])
            else:
                msg = data.get("message", "Unknown") if data else "No response"
                log.error("getCandleData failed: %s", msg)
                return None
        except Exception as e:
            log.error("getCandleData error: %s", e)
            return None

    def logout(self):
        """Terminate session cleanly."""
        if self.smart_api and self.logged_in:
            try:
                self.smart_api.terminateSession(self.client_id)
                log.info("Angel One session terminated")
            except Exception as e:
                log.warning("Angel One logout error: %s", e)
        self.logged_in = False
        self.auth_token = None
        self.refresh_token = None
        self.feed_token = None


# Module-level singleton accessor
def get_angel_auth():
    """Get the singleton AngelAuth instance."""
    return AngelAuth()
