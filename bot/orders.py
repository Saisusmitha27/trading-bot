"""
Order placement and result formatting layer.

Sits between the CLI and the raw BinanceFuturesClient — it:
  1. Validates all inputs.
  2. Delegates to the client.
  3. Returns a structured OrderResult for display.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .client import BinanceFuturesClient, BinanceAPIError
from .validators import (
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
    validate_stop_price,
)
from .logging_config import get_logger

logger = get_logger("orders")


@dataclass
class OrderRequest:
    """Validated, clean representation of what the user wants to place."""

    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: str = "GTC"
    reduce_only: bool = False

    def summary(self) -> str:
        lines = [
            "── Order Request ────────────────────────",
            f"  Symbol     : {self.symbol}",
            f"  Side       : {self.side}",
            f"  Type       : {self.order_type}",
            f"  Quantity   : {self.quantity}",
        ]
        if self.price is not None:
            lines.append(f"  Price      : {self.price}")
        if self.stop_price is not None:
            lines.append(f"  Stop Price : {self.stop_price}")
        if self.order_type == "LIMIT":
            lines.append(f"  TIF        : {self.time_in_force}")
        lines.append("─────────────────────────────────────────")
        return "\n".join(lines)


@dataclass
class OrderResult:
    """Parsed and formatted result returned to the CLI."""

    success: bool
    request: OrderRequest
    raw: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    # Key fields extracted for quick display
    order_id: int | None = None
    status: str = ""
    executed_qty: Decimal = Decimal("0")
    avg_price: Decimal = Decimal("0")

    @classmethod
    def from_response(cls, request: OrderRequest, raw: dict[str, Any]) -> "OrderResult":
        return cls(
            success=True,
            request=request,
            raw=raw,
            order_id=raw.get("orderId"),
            status=raw.get("status", ""),
            executed_qty=Decimal(str(raw.get("executedQty", "0"))),
            avg_price=Decimal(str(raw.get("avgPrice", "0"))),
        )

    @classmethod
    def from_error(cls, request: OrderRequest, error: str) -> "OrderResult":
        return cls(success=False, request=request, error=error)

    def display(self) -> str:
        lines = [self.request.summary()]
        if self.success:
            lines += [
                "── Order Response ───────────────────────",
                f"  Order ID     : {self.order_id}",
                f"  Status       : {self.status}",
                f"  Executed Qty : {self.executed_qty}",
                f"  Avg Price    : {self.avg_price if self.avg_price else 'N/A'}",
                "─────────────────────────────────────────",
                "✅  Order placed successfully.",
            ]
        else:
            lines += [
                "── Error ─────────────────────────────────",
                f"  {self.error}",
                "─────────────────────────────────────────",
                "❌  Order failed.",
            ]
        return "\n".join(lines)


def build_order_request(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: str | float | None = None,
    stop_price: str | float | None = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
) -> OrderRequest:
    """
    Validate raw CLI inputs and build a clean OrderRequest.

    Raises:
        ValueError: On any validation failure.
    """
    vsymbol = validate_symbol(symbol)
    vside = validate_side(side)
    vtype = validate_order_type(order_type)
    vqty = validate_quantity(quantity)
    vprice = validate_price(price, vtype)
    vstop = validate_stop_price(stop_price, vtype)

    return OrderRequest(
        symbol=vsymbol,
        side=vside,
        order_type=vtype,
        quantity=vqty,
        price=vprice,
        stop_price=vstop,
        time_in_force=time_in_force.upper(),
        reduce_only=reduce_only,
    )


def place_order(client: BinanceFuturesClient, req: OrderRequest) -> OrderResult:
    """
    Submit *req* to Binance and return an OrderResult.

    Catches API + network errors and folds them into a failed OrderResult
    so the caller doesn't need extra try/except.
    """
    logger.debug("Submitting order request: %s", req)
    try:
        raw = client.place_order(
            symbol=req.symbol,
            side=req.side,
            order_type=req.order_type,
            quantity=req.quantity,
            price=req.price,
            stop_price=req.stop_price,
            time_in_force=req.time_in_force,
            reduce_only=req.reduce_only,
        )
        logger.debug("Raw response: %s", json.dumps(raw, indent=2))

        # Testnet market orders sometimes return NEW immediately.
        # Wait briefly and re-fetch the real status.
        if req.order_type == "MARKET" and raw.get("status") == "NEW":
            import time
            time.sleep(1.5)
            try:
                raw = client.get_order(req.symbol, raw["orderId"])
                logger.debug("Re-fetched order status: %s", raw.get("status"))
            except Exception:
                pass  # Use original response if re-fetch fails

        result = OrderResult.from_response(req, raw)
        logger.info(
            "Order result | success=True orderId=%s status=%s execQty=%s avgPrice=%s",
            result.order_id,
            result.status,
            result.executed_qty,
            result.avg_price,
        )
        return result

    except BinanceAPIError as exc:
        msg = f"Binance API error {exc.code}: {exc.message}"
        logger.error(msg)
        return OrderResult.from_error(req, msg)

    except Exception as exc:
        msg = f"Unexpected error: {exc}"
        logger.exception(msg)
        return OrderResult.from_error(req, msg)