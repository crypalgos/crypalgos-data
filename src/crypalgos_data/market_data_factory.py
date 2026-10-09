"""
Factory and registry for managing exchange market data adapters.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Type

from .common.base_market_data import BaseMarketDataAdapter
from .exchanges.delta_market_data import DeltaMarketDataAdapter

logger = logging.getLogger(__name__)


class MarketDataFactory:
    """Registry and factory to manage and retrieve exchange adapters."""

    _adapters: Dict[str, Type[BaseMarketDataAdapter]] = {
        "delta": DeltaMarketDataAdapter,
    }

    @classmethod
    def get_adapter(cls, exchange: str, **kwargs) -> BaseMarketDataAdapter:
        """Return an initialized adapter for the given exchange."""
        name = exchange.lower()
        if name not in cls._adapters:
            available = ", ".join(sorted(cls._adapters.keys()))
            raise ValueError(
                f"Exchange '{exchange}' is not registered. "
                f"Available adapters: {available}"
            )
        return cls._adapters[name](**kwargs)

    @classmethod
    def register_adapter(cls, name: str, adapter_cls: Type[BaseMarketDataAdapter]) -> None:
        """Register a custom exchange adapter class at runtime."""
        cls._adapters[name.lower()] = adapter_cls
        logger.info("Registered market data adapter: %s", name)

    @classmethod
    def list_exchanges(cls) -> List[str]:
        """Return all registered exchange names."""
        return sorted(cls._adapters.keys())


def get_market_data(exchange: str, **kwargs) -> BaseMarketDataAdapter:
    """Convenience helper to quickly get an exchange adapter instance."""
    return MarketDataFactory.get_adapter(exchange, **kwargs)
