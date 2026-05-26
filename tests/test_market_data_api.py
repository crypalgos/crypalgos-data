"""
Tests for the Unified Market Data API and Market Data Factory.
"""

import pytest
from crypalgos_data.market_data_factory import MarketDataFactory, get_market_data
from crypalgos_data.market_data_api import UnifiedMarketDataAPI
from crypalgos_data.common.base_market_data import BaseMarketDataAdapter
from crypalgos_data.exchanges.delta_market_data import DeltaMarketDataAdapter


# ═══════════════════════════════════════════════════════════════════════════════
# Factory Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarketDataFactory:
    def test_get_delta_adapter(self):
        adapter = MarketDataFactory.get_adapter("delta")
        assert isinstance(adapter, DeltaMarketDataAdapter)
        assert adapter.exchange_id == "delta"

    def test_case_insensitive_lookup(self):
        adapter = MarketDataFactory.get_adapter("Delta")
        assert isinstance(adapter, DeltaMarketDataAdapter)

    def test_unknown_exchange_raises(self):
        with pytest.raises(ValueError, match="not registered"):
            MarketDataFactory.get_adapter("nonexistent")

    def test_list_exchanges(self):
        exchanges = MarketDataFactory.list_exchanges()
        assert "delta" in exchanges
        assert "binance" not in exchanges
        assert "coindcx" not in exchanges

    def test_convenience_function(self):
        adapter = get_market_data("delta")
        assert isinstance(adapter, DeltaMarketDataAdapter)

    def test_with_kwargs(self):
        adapter = get_market_data("delta", testnet=True)
        assert adapter.testnet is True

    def test_register_custom_adapter(self):
        """Test that custom adapters can be registered at runtime."""

        class MockAdapter(BaseMarketDataAdapter):
            exchange_id = "mock"

            async def fetch_instruments(self, instrument_type=None):
                return []

            async def fetch_ohlcv(self, symbol, timeframe, since_ms, limit=2000):
                return []

            async def fetch_trades(self, symbol, since_ms=None, limit=1000):
                return []

            def normalize_symbol(self, native_symbol):
                return native_symbol

            def denormalize_symbol(self, canonical_symbol, instrument_type=None):
                return canonical_symbol

        MarketDataFactory.register_adapter("mock", MockAdapter)
        adapter = MarketDataFactory.get_adapter("mock")
        assert isinstance(adapter, MockAdapter)
        assert adapter.exchange_id == "mock"

        # Clean up
        del MarketDataFactory._adapters["mock"]


# ═══════════════════════════════════════════════════════════════════════════════
# Unified API Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnifiedMarketDataAPI:
    def test_register_exchange(self):
        api = UnifiedMarketDataAPI()
        api.register_exchange("delta")
        assert "delta" in api.list_exchanges()

    def test_unregistered_exchange_raises(self):
        api = UnifiedMarketDataAPI()
        with pytest.raises(ValueError, match="not registered"):
            api._get_adapter("delta")

    def test_get_capabilities(self):
        api = UnifiedMarketDataAPI()
        api.register_exchange("delta")
        caps = api.get_capabilities("delta")
        assert "ohlcv" in caps
        assert "option_greeks" in caps


# ═══════════════════════════════════════════════════════════════════════════════
# Package Import Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPackageImports:
    """Verify all new exports are accessible from the top-level package."""

    def test_import_market_data_factory(self):
        from crypalgos_data import get_market_data, MarketDataFactory
        assert callable(get_market_data)
        assert hasattr(MarketDataFactory, "get_adapter")

    def test_import_unified_api(self):
        from crypalgos_data import UnifiedMarketDataAPI
        api = UnifiedMarketDataAPI()
        assert hasattr(api, "get_candles")
        assert hasattr(api, "get_funding")
        assert hasattr(api, "get_option_chain")

    def test_import_models(self):
        from crypalgos_data import (
            Instrument,
            InstrumentType,
            OptionType,
            FundingRate,
            MarkPrice,
            OpenInterest,
            OptionGreeks,
        )
        assert InstrumentType.PERPETUAL.value == "perpetual"

    def test_import_normalizer(self):
        from crypalgos_data import SymbolNormalizer
        norm = SymbolNormalizer(exchange_id="test")
        assert len(norm) == 0

    def test_backward_compatible_imports(self):
        """Ensure original trading API imports still work."""
        from crypalgos_data import (
            get_exchange,
            get_stream_client,
            BaseExchangeAPI,
            Candle,
            Ticker,
            Order,
            Position,
            Balance,
            Trade,
            StreamerManager,
            StreamSubscriber,
        )
        assert callable(get_exchange)
        assert callable(get_stream_client)
