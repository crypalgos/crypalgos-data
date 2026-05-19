# crypalgos-data

A high-performance, unified, and reusable market-data layer and execution interface for the CrypAlgos quantitative ecosystem.

---

## 🌟 Overview

`crypalgos-data` abstracts away exchange-specific complexities (such as REST request signatures, payload conventions, WebSocket connection states, symbol mapping, and PnL updates) and exposes a unified, type-safe interface for trading operations. 

It is designed to be easily packaged and deployed as a shared dependency inside other microservices (like data ingestion pipelines, backtesting engines, and execution brokers).

---

## 🚀 Key Features

*   **Unified Interface & Factories**: Dynamically load different exchange backends (e.g. `Delta Exchange`) via generic REST and WebSocket factory interfaces (`get_exchange` & `get_stream_client`).
*   **Normalized Models**: Standardized, high-performance Pydantic V2 models for `Candle`, `Ticker`, `Balance`, `Position`, and `Order`.
*   **Advanced Bracket Operations**: Robust support for standalone stop-loss/take-profit, entry bracket orders, edit brackets, and trailing stop-losses.
*   **ZeroMQ Broker Streaming**: Built-in async ZMQ publisher stream management.
*   **Packaged CLI Entrypoint**: Launch background data streamers via a single terminal command.
*   **Automated Pytest Coverage**: Complete 21-case mocked and integration test suite with 68% code coverage.

---

## 📦 Installation

Since this is a shared package in the CrypAlgos ecosystem, it can be installed directly from your GitHub repository:

### 1. From Terminal
```bash
# Using standard pip
pip install git+https://github.com/ashishjangde/crypalgos-data.git

# Using modern uv package manager
uv pip install git+https://github.com/ashishjangde/crypalgos-data.git
```

### 2. Inside `requirements.txt` or `pyproject.toml`
Add the following line to your project's dependency list:
```text
crypalgos-data @ git+https://github.com/ashishjangde/crypalgos-data.git
```

---

## 🔌 Quick Start

### 1. REST API & Dynamic Credentials Resolver
```python
import os
from crypalgos_data import get_exchange

# Credentials loaded dynamically from env or .env file
api = get_exchange(
    "delta", 
    api_key=os.getenv("DELTA_API_KEY"), 
    api_secret=os.getenv("DELTA_API_SECRET"), 
    testnet=True
)

async def main():
    # 1. Fetch unified tickers
    tickers = await api.fetch_tickers()
    for t in tickers:
        print(f"{t.symbol} Bid: {t.bid} | Ask: {t.ask} | Last: {t.last}")

    # 2. Place entry order with attached Bracket (Stop-Loss / Take-Profit)
    order = await api.place_order(
        symbol="BTCUSD",
        size=1,
        side="buy",
        order_type="limit",
        price=72000.0,
        sl_price=70000.0,
        tp_price=80000.0
    )
    print(f"Placed attached bracket order: ID {order.id}")
```

### ⚡️ 2. WebSocket Streaming Service (CLI Tool)
The package is pre-configured with a system-wide launcher. You can spin up a real-time data streamer microservice publishing to ZMQ simply by running:

```bash
# Launch streamer for Delta Exchange (will read CRYPALGOS_ZMQ_ADDRESS, keys and symbol variables)
crypalgos-streamer delta
```

---

## 🧪 Testing & Code Coverage

To run the automated mock and integration test suite locally, execute:

```bash
# Run pytest
uv run python -m pytest

# Run with full coverage reports
uv run python -m pytest --cov=src --cov-report=term-missing
```

---

## 📄 License
This project is proprietary. All rights reserved. Kept lean to protect trade execution algorithms.
