"""trading_bot.bot — Binance Futures client, order logic, and utilities."""

from .client import BinanceFuturesClient, BinanceAPIError
from .orders import OrderRequest, OrderResult, build_order_request, place_order
from .logging_config import setup_logging, get_logger
from .validators import (
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
)

__all__ = [
    "BinanceFuturesClient",
    "BinanceAPIError",
    "OrderRequest",
    "OrderResult",
    "build_order_request",
    "place_order",
    "setup_logging",
    "get_logger",
    "validate_symbol",
    "validate_side",
    "validate_order_type",
    "validate_quantity",
    "validate_price",
]
