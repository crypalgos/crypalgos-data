# Exchange Integration Guide

A practical guide on how to integrate new exchange adapters and real-time WebSocket clients into the CrypAlgos quantitative execution and market data platform.

---

## Architecture Overview

Adding support for an exchange involves implementing two primary layers:
1. **Historical/REST Market Data Adapter**: Inherits from `BaseMarketDataAdapter` to ingest candles, trades, Greeks, and order books.
2. **WebSocket Stream Client**: Inherits from `BaseExchangeClient` to stream real-time events to the ZeroMQ broker.

---

## 1. Implementing the Market Data Adapter

Create a new file `src/crypalgos_data/exchanges/{name}_market_data.py`:

```python
from __future__ import annotations

from typing import List, Optional, Set
from ..common.base_market_data import BaseMarketDataAdapter
from ..common.market_data_models import (
    FundingRate,
    Instrument,
    InstrumentType,
    MarkPrice,
    OpenInterest,
    OptionGreeks,
)
from ..common.models import Candle, Trade
from ..common.symbol_normalizer import SymbolNormalizer


class MyExchangeMarketDataAdapter(BaseMarketDataAdapter):
    exchange_id: str = "myexchange"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False):
        self.base_url = "https://api.myexchange.com"
        self.normalizer = SymbolNormalizer(exchange_id=self.exchange_id)

    # --- Required Abstract Methods ---

    async def fetch_instruments(self, instrument_type: Optional[InstrumentType] = None) -> List[Instrument]:
        """Fetch active products, map them to canonical Instrument models, and populate self.normalizer."""
        # 1. Retrieve products via REST API
        # 2. Map and append canonical Instrument models
        # 3. Call self.normalizer.build_from_instruments(instruments)
        pass

    async def fetch_ohlcv(self, symbol: str, timeframe: str, since_ms: int, limit: int = 2000) -> List[Candle]:
        """Fetch historical candles with pagination."""
        pass

    async def fetch_trades(self, symbol: str, since_ms: Optional[int] = None, limit: int = 1000) -> List[Trade]:
        """Fetch recent public trade history."""
        pass

    def normalize_symbol(self, native_symbol: str) -> str:
        """Convert native symbol to canonical (e.g. 'BTCUSDT' -> 'BTC')."""
        cached = self.normalizer.to_canonical(native_symbol)
        return cached if cached else native_symbol

    def denormalize_symbol(self, canonical_symbol: str, instrument_type: InstrumentType = InstrumentType.PERPETUAL) -> str:
        """Convert canonical symbol back to native format."""
        cached = self.normalizer.to_native(canonical_symbol, instrument_type)
        return cached if cached else f"{canonical_symbol}USDT"

    # --- Optional Capabilities (Override as Supported) ---

    async def fetch_funding(self, symbol: str, since_ms: Optional[int] = None, limit: int = 500) -> List[FundingRate]:
        return []

    async def fetch_mark_price(self, symbol: str) -> Optional[MarkPrice]:
        return None

    async def fetch_open_interest(self, symbol: str) -> Optional[OpenInterest]:
        return None

    async def fetch_option_greeks(self, symbol: str) -> Optional[OptionGreeks]:
        return None

    def supported_capabilities(self) -> Set[str]:
        return {"ohlcv", "trades"}
```

---

## 2. Implementing the WebSocket Stream Client

Create a new file `src/crypalgos_data/stream/exchanges/{name}.py`:

```python
from typing import List, Optional, Union, Tuple
from ...common.base_stream import BaseExchangeClient
from ...common.models import Candle, Ticker, Trade, Order, Position, Balance
from ...common.market_data_models import OptionGreeks, MarkPrice, OpenInterest


class MyExchangeStreamClient(BaseExchangeClient):
    """Real-time WebSocket connection client mapping to ZeroMQ Broker topics."""

    def __init__(self, broker, symbols: List[str] = [], testnet: bool = False):
        url = "wss://stream.myexchange.com"
        super().__init__(broker, "myexchange", url)
        self.symbols = symbols

    def get_subscription_payload(self) -> dict:
        """Subscription frames (e.g. trades, candles, ticker streams)."""
        return {
            "op": "subscribe",
            "args": [f"trade:{s}" for s in self.symbols]
        }

    def normalize_message(self, message: dict) -> Optional[Union[Tuple[str, any], List[Tuple[str, any]]]]:
        """
        Normalize raw event messages.
        Returns topic-suffix and dataclass tuples matching standard broker routing.
        """
        msg_type = message.get("type")
        if msg_type == "trade":
            return ("trade", Trade(
                exchange="myexchange",
                symbol=message["symbol"],
                price=float(message["price"]),
                amount=float(message["size"]),
                timestamp=int(message["time"])
            ))
        return None
```

---

## 3. Registering Your Adapter

### REST/Historical Adapter Registration
Add your adapter class import to `src/crypalgos_data/market_data_factory.py` and register it inside the `_adapters` lookup dictionary:

```python
from .exchanges.delta_market_data import DeltaMarketDataAdapter
from .exchanges.myexchange_market_data import MyExchangeMarketDataAdapter

class MarketDataFactory:
    _adapters: Dict[str, Type[BaseMarketDataAdapter]] = {
        "delta": DeltaMarketDataAdapter,
        "myexchange": MyExchangeMarketDataAdapter,
    }
```

### WebSocket Streamer Registration
Add your client class import to `src/crypalgos_data/factory.py` and register it inside `ExchangeFactory._stream_clients`:

```python
from .stream.exchanges.delta import DeltaExchangeClient
from .stream.exchanges.myexchange import MyExchangeStreamClient

class ExchangeFactory:
    _stream_clients: Dict[str, Type[BaseExchangeClient]] = {
        "delta": DeltaExchangeClient,
        "myexchange": MyExchangeStreamClient,
    }
```

---

## 4. Symbol Formatting Scopes

Map native formatting into high-level canonical structures consistently:

| Exchange | Native Format | Canonical Asset | Base / Quote |
| :--- | :--- | :--- | :--- |
| **Delta** | `BTCUSD` (Futures) / `C-BTC-85000-310726` (Option) | `BTC` | `BTC` / `USD` |

---

## 5. Sanity Verification Checklist

Before pushing new exchange integrations or trading modules to production:

- [ ] **Tests Green**: Ensure unit testing coverage succeeds by running:
  ```bash
  PYTHONPATH=src python -m pytest
  ```
- [ ] **Defensive Heartbeat Safeguards**: Verify that pings/sub-updates on WebSockets are ignored securely via `normalize_message` without throwing `TypeError`.
- [ ] **Real-time Greeks/OI/Mark Pricing**: Check that options or derivatives channels return a list of unpacked tuples to dispatch live `mark_price`, `open_interest`, and `option_greeks` topics cleanly.
- [ ] **Dynamic Bracket Constraints (SL/TP)**: Place buy limit orders far below market price with attached trigger metrics (`sl_price` and `tp_price`) on Testnet and visually confirm the brackets in your Exchange Dashboard before going live.
