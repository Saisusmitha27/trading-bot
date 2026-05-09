"""
Input validation helpers for trading bot CLI arguments.
All functions raise ValueError with human-readable messages on bad input.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}

# Reasonable sanity bounds (not enforced by Binance itself here)
MIN_QUANTITY = Decimal("0.001")
MAX_QUANTITY = Decimal("1_000_000")


def validate_symbol(symbol: str) -> str:
    """Normalise and validate a trading symbol."""
    s = symbol.strip().upper()
    if not s:
        raise ValueError("Symbol cannot be empty.")
    if len(s) < 3 or not s.isalnum():
        raise ValueError(
            f"Invalid symbol '{symbol}'. Expected alphanumeric (e.g. BTCUSDT)."
        )
    return s


def validate_side(side: str) -> str:
    """Validate order side."""
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return s


def validate_order_type(order_type: str) -> str:
    """Validate order type."""
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return t


def validate_quantity(quantity: str | float | Decimal) -> Decimal:
    """Parse and validate order quantity."""
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Invalid quantity '{quantity}'. Must be a positive number.")
    if qty <= 0:
        raise ValueError(f"Quantity must be greater than zero, got {qty}.")
    if qty < MIN_QUANTITY:
        raise ValueError(f"Quantity {qty} is below minimum allowed ({MIN_QUANTITY}).")
    if qty > MAX_QUANTITY:
        raise ValueError(f"Quantity {qty} exceeds maximum allowed ({MAX_QUANTITY}).")
    return qty


def validate_price(price: str | float | Decimal | None, order_type: str) -> Decimal | None:
    """
    Validate limit price.
    - Required (and > 0) for LIMIT and STOP_MARKET orders.
    - Must be None for MARKET orders.
    """
    if order_type == "MARKET":
        if price is not None:
            raise ValueError("Price must not be provided for MARKET orders.")
        return None

    if price is None:
        raise ValueError(f"Price is required for {order_type} orders.")

    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValueError(f"Invalid price '{price}'. Must be a positive number.")
    if p <= 0:
        raise ValueError(f"Price must be greater than zero, got {p}.")
    return p


def validate_stop_price(
    stop_price: str | float | Decimal | None, order_type: str
) -> Decimal | None:
    """Validate stop price for STOP_MARKET orders."""
    if order_type != "STOP_MARKET":
        return None
    if stop_price is None:
        raise ValueError("stop_price is required for STOP_MARKET orders.")
    try:
        sp = Decimal(str(stop_price))
    except InvalidOperation:
        raise ValueError(f"Invalid stop_price '{stop_price}'. Must be a positive number.")
    if sp <= 0:
        raise ValueError(f"stop_price must be greater than zero, got {sp}.")
    return sp
