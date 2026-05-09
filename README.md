# Binance Futures Testnet Trading Bot

A clean, production-style Python CLI for placing orders on Binance USDT-M Futures Testnet.

## Features

| Capability | Detail |
|---|---|
| Order types | MARKET, LIMIT, STOP_MARKET (bonus) |
| Sides | BUY & SELL |
| Validation | Symbol, side, type, quantity, price — all validated before any API call |
| Logging | Rotating file log (`logs/trading_bot.log`) + concise console output |
| Error handling | API errors, network failures, invalid input — all caught & reported clearly |
| Structure | Separate `client`, `orders`, `validators`, `logging_config` layers |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package exports
│   ├── client.py            # Binance REST client (signing, retries, HTTP)
│   ├── orders.py            # Order logic + result formatting
│   ├── validators.py        # Input validation helpers
│   └── logging_config.py   # Rotating file + console logging setup
├── logs/
│   └── trading_bot.log      # Auto-created on first run
├── cli.py                   # CLI entry point (argparse)
├── .env.example             # Credential template
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet Credentials

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in with your GitHub account
3. Click **"API Key"** → generate a new key pair
4. Copy the **API Key** and **Secret Key**

### 2. Install Dependencies

```bash
# Python 3.8+ required
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Credentials

```bash
cp .env.example .env
# Edit .env and set your keys:
#   BINANCE_API_KEY=...
#   BINANCE_API_SECRET=...
```

Alternatively, export them directly:

```bash
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
```

---

## Usage

### Place a Market Order

```bash
# BUY 0.01 BTC at market price
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01

# SELL 0.5 ETH at market price
python cli.py place --symbol ETHUSDT --side SELL --type MARKET --qty 0.5
```

### Place a Limit Order

```bash
# SELL 0.1 ETH at $2,800 (rests on book until filled or cancelled)
python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --qty 0.1 --price 2800

# BUY 0.01 BTC at $58,000 with Immediate-or-Cancel
python cli.py place --symbol BTCUSDT --side BUY --type LIMIT --qty 0.01 --price 58000 --tif IOC
```

### Place a Stop-Market Order *(bonus)*

```bash
# Trigger a market SELL if BTC drops to $55,000
python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.01 --stop-price 55000
```

### View Account Balances

```bash
python cli.py account

# Full JSON response:
python cli.py account --raw
```

### List Open Orders

```bash
python cli.py open-orders
python cli.py open-orders --symbol BTCUSDT
```

### Print Raw API Response

Append `--raw` to any `place` command:

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01 --raw
```

---

## Sample Output

### Market Order

```
── Order Request ────────────────────────
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.01
─────────────────────────────────────────

── Order Response ───────────────────────
  Order ID     : 4751839201
  Status       : FILLED
  Executed Qty : 0.01
  Avg Price    : 62345.10
─────────────────────────────────────────
✅  Order placed successfully.
```

### Limit Order

```
── Order Request ────────────────────────
  Symbol     : ETHUSDT
  Side       : SELL
  Type       : LIMIT
  Quantity   : 0.1
  Price      : 2800
  TIF        : GTC
─────────────────────────────────────────

── Order Response ───────────────────────
  Order ID     : 4751840088
  Status       : NEW
  Executed Qty : 0
  Avg Price    : N/A
─────────────────────────────────────────
✅  Order placed successfully.
```

---

## Logging

All API requests, responses, and errors are written to `logs/trading_bot.log` (rotating, max 5 MB × 3 backups).

Console output shows INFO-level messages only. The log file captures DEBUG-level detail including full request params and truncated response bodies.

```
2025-05-08T11:02:01 | INFO     | trading_bot.client | Placing BUY MARKET order | symbol=BTCUSDT qty=0.01 price=N/A
2025-05-08T11:02:02 | INFO     | trading_bot.client | Order placed | orderId=4751839201 status=FILLED
2025-05-08T11:02:02 | INFO     | trading_bot.orders | Order result | success=True orderId=4751839201 status=FILLED execQty=0.01 avgPrice=62345.10
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing credentials | Exit with clear message before any API call |
| Invalid symbol / side / type | Validation error printed; exits code 1 |
| Missing price for LIMIT | Caught at validation, not at API layer |
| Binance API error (e.g. -1121 invalid symbol) | Caught, error code + message displayed |
| Network timeout / connection refused | Caught, friendly message; logged |
| Non-JSON / unexpected response | Caught and logged |

---

## Assumptions

- Testnet only — base URL is hardcoded to `https://testnet.binancefuture.com`.
- Hedge mode is **not** assumed; all orders use `positionSide=BOTH` (one-way mode default).
- Quantity precision is passed as-is; if Binance rejects due to step-size, the error is surfaced verbatim. For production use, symbol filters from `/fapi/v1/exchangeInfo` should be applied.
- `time_in_force` defaults to `GTC` for LIMIT orders; override with `--tif IOC` or `--tif FOK`.
- No `python-binance` library dependency — all calls use `requests` directly, keeping the dependency footprint minimal and making the signing logic explicit and auditable.
