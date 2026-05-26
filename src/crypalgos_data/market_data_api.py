"""
Unified entry point for fetching market data across different exchanges.
"""

import logging
from typing import Dict, List, Optional, Set

from .common.base_market_data import BaseMarketDataAdapter
from .common.market_data_models import (
    FundingRate,
    Instrument,
    InstrumentType,
    MarkPrice,
    OpenInterest,
    OptionGreeks,
)
from .common.models import Candle, Trade
from .market_data_factory import MarketDataFactory

logger = logging.getLogger(__name__)


class UnifiedMarketDataAPI:
    """
    Unified access layer that routes queries to appropriate exchange adapters.
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, BaseMarketDataAdapter] = {}

    def register_exchange(self, exchange: str, **kwargs) -> None:
        """Register and initialize an exchange adapter."""
        name = exchange.lower()
        if name in self._adapters:
            logger.warning("Exchange '%s' already registered — replacing", name)

        adapter = MarketDataFactory.get_adapter(name, **kwargs)
        self._adapters[name] = adapter
        logger.info("Registered exchange: %s (capabilities: %s)", name, adapter.supported_capabilities())

    def _get_adapter(self, exchange: str) -> BaseMarketDataAdapter:
        name = exchange.lower()
        if name not in self._adapters:
            available = ", ".join(sorted(self._adapters.keys())) or "(none)"
            raise ValueError(
                f"Exchange '{exchange}' is not registered. "
                f"Call register_exchange() first. Registered: {available}"
            )
        return self._adapters[name]

    async def get_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str = "1m",
        since_ms: int = 0,
        limit: int = 2000,
    ) -> List[Candle]:
        """Fetch OHLCV candles from a specific exchange."""
        adapter = self._get_adapter(exchange)
        return await adapter.fetch_ohlcv(symbol, timeframe, since_ms, limit)

    async def get_funding(
        self,
        exchange: str,
        symbol: str,
        since_ms: Optional[int] = None,
        limit: int = 500,
    ) -> List[FundingRate]:
        """Fetch funding rate history for a perpetual contract."""
        adapter = self._get_adapter(exchange)
        if "funding" not in adapter.supported_capabilities():
            logger.warning("Exchange '%s' does not support funding rates", exchange)
            return []
        return await adapter.fetch_funding(symbol, since_ms, limit)

    async def get_instruments(
        self,
        exchange: str,
        instrument_type: Optional[InstrumentType] = None,
    ) -> List[Instrument]:
        """Fetch all instruments from an exchange."""
        adapter = self._get_adapter(exchange)
        return await adapter.fetch_instruments(instrument_type)

    async def get_option_chain(
        self,
        exchange: str,
        base_asset: str,
    ) -> List[Instrument]:
        """Fetch all option instruments for a given base asset."""
        adapter = self._get_adapter(exchange)
        if "option_greeks" not in adapter.supported_capabilities():
            logger.warning("Exchange '%s' does not support options", exchange)
            return []

        all_instruments = await adapter.fetch_instruments()
        return [
            inst
            for inst in all_instruments
            if inst.canonical_symbol == base_asset.upper()
            and inst.instrument_type in (InstrumentType.CALL_OPTION, InstrumentType.PUT_OPTION)
        ]

    async def get_mark_price(
        self,
        exchange: str,
        symbol: str,
    ) -> Optional[MarkPrice]:
        """Fetch current mark price for a derivatives instrument."""
        adapter = self._get_adapter(exchange)
        if "mark_price" not in adapter.supported_capabilities():
            return None
        return await adapter.fetch_mark_price(symbol)

    async def get_open_interest(
        self,
        exchange: str,
        symbol: str,
    ) -> Optional[OpenInterest]:
        """Fetch current open interest for a derivatives instrument."""
        adapter = self._get_adapter(exchange)
        if "open_interest" not in adapter.supported_capabilities():
            return None
        return await adapter.fetch_open_interest(symbol)

    async def get_trades(
        self,
        exchange: str,
        symbol: str,
        since_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Trade]:
        """Fetch recent public trades."""
        adapter = self._get_adapter(exchange)
        return await adapter.fetch_trades(symbol, since_ms, limit)

    async def get_option_greeks(
        self,
        exchange: str,
        symbol: str,
    ) -> Optional[OptionGreeks]:
        """Fetch Greeks for an options instrument."""
        adapter = self._get_adapter(exchange)
        if "option_greeks" not in adapter.supported_capabilities():
            return None
        return await adapter.fetch_option_greeks(symbol)

    def get_capabilities(self, exchange: str) -> Set[str]:
        """Return the set of supported capabilities for an exchange."""
        return self._get_adapter(exchange).supported_capabilities()

    def list_exchanges(self) -> List[str]:
        """Return all registered exchange names."""
        return sorted(self._adapters.keys())
