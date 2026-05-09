#!/usr/bin/env python3
"""
cli.py — Binance Futures Testnet Trading Bot CLI

Entry point for placing orders from the command line.

Usage examples:
    python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01
    python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --qty 0.1 --price 2800
    python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.01 --stop-price 55000
    python cli.py account
    python cli.py open-orders --symbol BTCUSDT
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Make sure project root is on path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot.logging_config import setup_logging, get_logger
from bot.client import BinanceFuturesClient, BinanceAPIError
from bot.orders import build_order_request, place_order

# ── Bootstrap ────────────────────────────────────────────────────────────────

load_dotenv()  # Load .env if present
logger = setup_logging()  # Configure logging before anything else
log = get_logger("cli")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client() -> BinanceFuturesClient:
    """Build client from environment variables."""
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        print(
            "\n❌  Missing credentials.\n"
            "    Set BINANCE_API_KEY and BINANCE_API_SECRET in your environment\n"
            "    or in a .env file in the project root.\n"
        )
        sys.exit(1)

    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


def _print_json(data: dict | list) -> None:
    print(json.dumps(data, indent=2))


# ── Sub-command handlers ──────────────────────────────────────────────────────

def cmd_place(args: argparse.Namespace) -> int:
    """Handle the 'place' sub-command."""
    client = _get_client()
    log.info(
        "CLI place | symbol=%s side=%s type=%s qty=%s price=%s stop=%s",
        args.symbol, args.side, args.type, args.qty, args.price, args.stop_price,
    )

    # Validate & build request
    try:
        req = build_order_request(
            symbol=args.symbol,
            side=args.side,
            order_type=args.type,
            quantity=args.qty,
            price=args.price,
            stop_price=args.stop_price,
            time_in_force=args.tif,
            reduce_only=args.reduce_only,
        )
    except ValueError as exc:
        print(f"\n❌  Validation error: {exc}\n")
        log.error("Validation error: %s", exc)
        return 1

    # Print request summary
    print(f"\n{req.summary()}")

    # Execute
    result = place_order(client, req)

    # Print result
    print(result.display())

    if args.raw and result.raw:
        print("\n── Raw Response ─────────────────────────")
        _print_json(result.raw)

    return 0 if result.success else 1


def cmd_account(args: argparse.Namespace) -> int:
    """Handle the 'account' sub-command."""
    client = _get_client()
    log.info("CLI account info requested.")
    try:
        info = client.get_account()
        assets = [a for a in info.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
        print("\n── Account Balances (non-zero) ───────────")
        for a in assets:
            print(f"  {a['asset']:<8} wallet={a['walletBalance']:<16} unrealised PnL={a.get('unrealizedProfit', 'N/A')}")
        if not assets:
            print("  (no balances)")
        print("─────────────────────────────────────────\n")
        if args.raw:
            _print_json(info)
        return 0
    except BinanceAPIError as exc:
        print(f"\n❌  {exc}\n")
        log.error("Account fetch failed: %s", exc)
        return 1


def cmd_open_orders(args: argparse.Namespace) -> int:
    """Handle the 'open-orders' sub-command."""
    client = _get_client()
    symbol = args.symbol or None
    log.info("CLI open-orders | symbol=%s", symbol)
    try:
        orders = client.get_open_orders(symbol=symbol)
        print(f"\n── Open Orders ({len(orders)}) ────────────────────")
        for o in orders:
            print(
                f"  {o['orderId']} | {o['symbol']} {o['side']} {o['type']} "
                f"qty={o['origQty']} price={o.get('price','N/A')} status={o['status']}"
            )
        if not orders:
            print("  (none)")
        print("─────────────────────────────────────────\n")
        return 0
    except BinanceAPIError as exc:
        print(f"\n❌  {exc}\n")
        log.error("Open orders fetch failed: %s", exc)
        return 1


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  Market BUY:
    python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01

  Limit SELL:
    python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --qty 0.1 --price 2800

  Stop-Market SELL (bonus):
    python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.01 --stop-price 55000

  Account balances:
    python cli.py account

  Open orders:
    python cli.py open-orders --symbol BTCUSDT
        """,
    )
    parser.add_argument(
        "--raw", action="store_true", help="Print raw JSON API response at the end."
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── place ──
    p_place = sub.add_parser("place", help="Place a new order.")
    p_place.add_argument("--symbol", required=True, metavar="SYMBOL",
                         help="Trading pair, e.g. BTCUSDT")
    p_place.add_argument("--side", required=True, choices=["BUY", "SELL"],
                         help="Order side")
    p_place.add_argument("--type", required=True,
                         choices=["MARKET", "LIMIT", "STOP_MARKET"],
                         help="Order type")
    p_place.add_argument("--qty", required=True, type=str, metavar="QUANTITY",
                         help="Order quantity (base asset)")
    p_place.add_argument("--price", default=None, type=str,
                         help="Limit price (required for LIMIT orders)")
    p_place.add_argument("--stop-price", dest="stop_price", default=None, type=str,
                         help="Stop trigger price (required for STOP_MARKET orders)")
    p_place.add_argument("--tif", default="GTC", choices=["GTC", "IOC", "FOK"],
                         help="Time-in-force for LIMIT orders (default: GTC)")
    p_place.add_argument("--reduce-only", dest="reduce_only", action="store_true",
                         help="Mark order as reduce-only")
    p_place.add_argument("--raw", action="store_true",
                         help="Print raw JSON API response")

    # ── account ──
    p_acc = sub.add_parser("account", help="Show account balances.")
    p_acc.add_argument("--raw", action="store_true", help="Print full JSON")

    # ── open-orders ──
    p_oo = sub.add_parser("open-orders", help="List open orders.")
    p_oo.add_argument("--symbol", default=None, metavar="SYMBOL",
                      help="Filter by symbol (optional)")

    return parser


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "place": cmd_place,
        "account": cmd_account,
        "open-orders": cmd_open_orders,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args))


if __name__ == "__main__":
    main()
