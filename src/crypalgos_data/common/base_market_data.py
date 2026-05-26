"""
Abstract base class for exchange market data adapters.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Set

from .market_data_models import (
    FundingRate,
    Instrument,
    InstrumentType,
    MarkPrice,
    OpenInterest,
    OptionGreeks,
)
from .models import Candle, Trade

logger = logging.getLogger(__name__)


class BaseMarketDataAdapter(ABC):
    """Exchange-agnostic market data adapter."""

    exchange_id: str = ""

    @abstractmethod
    async def fetch_instruments(
        self,
        instrument_type: Optional[InstrumentType] = None,
    ) -> List[Instrument]:
        """Fetch all tradable instruments from the exchange."""
        pass

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since_ms: int,
        limit: int = 2000,
    ) -> List[Candle]:
        """Fetch historical OHLCV candles."""
        pass

    @abstractmethod
    async def fetch_trades(
        self,
        symbol: str,
        since_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Trade]:
        """Fetch recent public trades."""
        pass

    async def fetch_funding(
        self,
        symbol: str,
        since_ms: Optional[int] = None,
        limit: int = 500,
    ) -> List[FundingRate]:
        """Fetch funding rate history for perpetual contracts."""
        return []

    async def fetch_mark_price(self, symbol: str) -> Optional[MarkPrice]:
        """Fetch current mark price for a derivatives instrument."""
        return None

    async def fetch_open_interest(self, symbol: str) -> Optional[OpenInterest]:
        """Fetch current open interest for a derivatives instrument."""
        return None

    async def fetch_option_greeks(self, symbol: str) -> Optional[OptionGreeks]:
        """Fetch Greeks for an options instrument."""
        return None

    @abstractmethod
    def normalize_symbol(self, native_symbol: str) -> str:
        """Convert exchange-native symbol to a canonical symbol (e.g. BTCUSD -> BTC)."""
        pass

    @abstractmethod
    def denormalize_symbol(
        self,
        canonical_symbol: str,
        instrument_type: InstrumentType = InstrumentType.PERPETUAL,
    ) -> str:
        """Convert canonical symbol back to exchange-native symbol."""
        pass

    def websocket_subscriptions(self, symbols: List[str]) -> List[dict]:
        """Generate WebSocket subscription payloads for the given symbols."""
        return []

    def supported_capabilities(self) -> Set[str]:
        """Report which capabilities this adapter supports."""
        return {"ohlcv", "trades"}
