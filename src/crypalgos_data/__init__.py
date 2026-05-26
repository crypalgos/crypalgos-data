"""
crypalgos-data — Unified market data layer and execution interface.

Exports both the original trading API (get_exchange, get_stream_client)
and the new market data platform (get_market_data, UnifiedMarketDataAPI).
"""

# ── Original trading API (unchanged) ─────────────────────────────────────────
from .factory import get_exchange, get_stream_client
from .common.base_api import BaseExchangeAPI
from .common.models import Candle, Ticker, Order, Position, Balance, Trade
from .stream.manager import StreamerManager
from .stream.subscriber import StreamSubscriber

# ── Market data platform (new) ───────────────────────────────────────────────
from .market_data_factory import get_market_data, MarketDataFactory
from .market_data_api import UnifiedMarketDataAPI
from .common.base_market_data import BaseMarketDataAdapter
from .common.market_data_models import (
    Instrument,
    InstrumentType,
    OptionType,
    FundingRate,
    MarkPrice,
    OpenInterest,
    OptionGreeks,
)
from .common.symbol_normalizer import SymbolNormalizer

__all__ = [
    # ── Trading API ──
    "get_exchange",
    "get_stream_client",
    "BaseExchangeAPI",
    "Candle",
    "Ticker",
    "Order",
    "Position",
    "Balance",
    "Trade",
    "StreamerManager",
    "StreamSubscriber",
    # ── Market Data Platform ──
    "get_market_data",
    "MarketDataFactory",
    "UnifiedMarketDataAPI",
    "BaseMarketDataAdapter",
    "Instrument",
    "InstrumentType",
    "OptionType",
    "FundingRate",
    "MarkPrice",
    "OpenInterest",
    "OptionGreeks",
    "SymbolNormalizer",
]
