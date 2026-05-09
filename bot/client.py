"""
Low-level Binance Futures Testnet REST client.

Handles:
  - HMAC-SHA256 request signing
  - Timestamping
  - HTTP request execution with retries
  - Raw API error surfacing
"""

from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logging_config import get_logger

logger = get_logger("client")

BASE_URL = "https://testnet.binancefuture.com"

# Retry on transient server errors / connection issues
_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST", "DELETE"],
)


class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx response or an error code payload."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceFuturesClient:
    """
    Minimal async-free client for the Binance USD-M Futures REST API.

    Args:
        api_key:    Testnet API key.
        api_secret: Testnet API secret.
        base_url:   Override the default testnet base URL if needed.
        timeout:    HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = BASE_URL,
        timeout: int = 10,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must not be empty.")

        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        adapter = HTTPAdapter(max_retries=_RETRY_STRATEGY)
        self._session = requests.Session()
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self._session.headers.update({"X-MBX-APIKEY": self._api_key})

        logger.debug("BinanceFuturesClient initialised (base_url=%s).", self._base_url)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        """Append a server timestamp and HMAC-SHA256 signature to *params*."""
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(
            self._api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = sig
        return params

    def _request(
        self, method: str, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute a signed HTTP request.

        Args:
            method:   'GET' | 'POST' | 'DELETE'
            endpoint: API path, e.g. '/fapi/v1/order'
            params:   Query/body parameters (will be signed).

        Returns:
            Parsed JSON response as a dict.

        Raises:
            BinanceAPIError: On Binance-level errors.
            requests.RequestException: On network/transport errors.
        """
        params = params or {}
        signed = self._sign(params)
        url = f"{self._base_url}{endpoint}"

        logger.debug("→ %s %s  params=%s", method, endpoint, {k: v for k, v in signed.items() if k != "signature"})

        try:
            if method == "GET":
                resp = self._session.get(url, params=signed, timeout=self._timeout)
            elif method == "POST":
                resp = self._session.post(url, params=signed, timeout=self._timeout)
            elif method == "DELETE":
                resp = self._session.delete(url, params=signed, timeout=self._timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network error contacting %s: %s", url, exc)
            raise
        except requests.exceptions.Timeout:
            logger.error("Request to %s timed out after %ss.", url, self._timeout)
            raise

        logger.debug("← HTTP %s  body=%s", resp.status_code, resp.text[:500])

        try:
            data: dict = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise BinanceAPIError(-1, f"Non-JSON response: {resp.text[:200]}")

        # Binance returns error details even on 4xx with a JSON body
        if "code" in data and data["code"] != 200:
            raise BinanceAPIError(data["code"], data.get("msg", "Unknown error"))

        resp.raise_for_status()
        return data

    # ── Public API methods ────────────────────────────────────────────────────

    def get_server_time(self) -> int:
        """Return Binance server timestamp in milliseconds."""
        data = self._request("GET", "/fapi/v1/time")
        return data["serverTime"]

    def get_exchange_info(self) -> dict[str, Any]:
        """Return exchange metadata (symbols, filters, etc.)."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def get_account(self) -> dict[str, Any]:
        """Return account information including balances."""
        return self._request("GET", "/fapi/v2/account")

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        """
        Place a new futures order.

        Args:
            symbol:        Trading pair, e.g. 'BTCUSDT'.
            side:          'BUY' or 'SELL'.
            order_type:    'MARKET', 'LIMIT', or 'STOP_MARKET'.
            quantity:      Order quantity (base asset).
            price:         Limit price (required for LIMIT orders).
            stop_price:    Trigger price (required for STOP_MARKET orders).
            time_in_force: 'GTC' | 'IOC' | 'FOK' (ignored for MARKET).
            reduce_only:   If True, order can only reduce a position.

        Returns:
            Raw order response dict from Binance.
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),
        }

        if order_type == "LIMIT":
            if price is None:
                raise ValueError("price is required for LIMIT orders.")
            params["price"] = str(price)
            params["timeInForce"] = time_in_force

        if order_type == "STOP_MARKET":
            if stop_price is None:
                raise ValueError("stop_price is required for STOP_MARKET orders.")
            params["stopPrice"] = str(stop_price)

        if reduce_only:
            params["reduceOnly"] = "true"

        logger.info(
            "Placing %s %s order | symbol=%s qty=%s price=%s",
            side,
            order_type,
            symbol,
            quantity,
            price or stop_price or "N/A",
        )

        response = self._request("POST", "/fapi/v1/order", params)
        logger.info(
            "Order placed | orderId=%s status=%s",
            response.get("orderId"),
            response.get("status"),
        )
        return response

    def get_order(self, symbol: str, order_id: int) -> dict[str, Any]:
        """Fetch a single order by orderId."""
        params = {"symbol": symbol, "orderId": order_id}
        return self._request("GET", "/fapi/v1/order", params)

    def cancel_order(self, symbol: str, order_id: int) -> dict[str, Any]:
        """Cancel an open order by orderId."""
        params = {"symbol": symbol, "orderId": order_id}
        logger.info("Cancelling orderId=%s for %s", order_id, symbol)
        return self._request("DELETE", "/fapi/v1/order", params)

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Return all open orders, optionally filtered by symbol."""
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params)  # type: ignore[return-value]