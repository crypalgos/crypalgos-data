"""
Tests for the Delta Exchange market data adapter.
"""

import pytest
from crypalgos_data.exchanges.delta_market_data import (
    DeltaMarketDataAdapter,
    _extract_base_asset,
)
from crypalgos_data.common.market_data_models import InstrumentType


# ═══════════════════════════════════════════════════════════════════════════════
# Base Asset Extraction (heuristic parser)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractBaseAsset:
    def test_perpetual_usd(self):
        assert _extract_base_asset("BTCUSD") == "BTC"
        assert _extract_base_asset("ETHUSD") == "ETH"
        assert _extract_base_asset("SOLUSD") == "SOL"
        assert _extract_base_asset("XRPUSD") == "XRP"

    def test_perpetual_usdt(self):
        assert _extract_base_asset("BTCUSDT") == "BTC"
        assert _extract_base_asset("ETHUSDT") == "ETH"

    def test_futures_with_date(self):
        assert _extract_base_asset("BTCUSD_250627") == "BTC"
        assert _extract_base_asset("ETHUSD_250328") == "ETH"

    def test_call_option_format(self):
        assert _extract_base_asset("C-BTC-65000-250627") == "BTC"
        assert _extract_base_asset("C-ETH-4000-250328") == "ETH"

    def test_put_option_format(self):
        assert _extract_base_asset("P-BTC-60000-250627") == "BTC"
        assert _extract_base_asset("P-SOL-200-250328") == "SOL"

    def test_single_asset_fallback(self):
        # If no suffix matches, return uppercase
        assert _extract_base_asset("DOGE") == "DOGE"


# ═══════════════════════════════════════════════════════════════════════════════
# Adapter Initialization
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeltaAdapterInit:
    def test_default_init(self):
        adapter = DeltaMarketDataAdapter()
        assert adapter.exchange_id == "delta"
        assert adapter.testnet is False
        assert "api.india.delta.exchange" in adapter.base_url

    def test_testnet_init(self):
        adapter = DeltaMarketDataAdapter(testnet=True)
        assert adapter.testnet is True
        assert "testnet" in adapter.base_url

    def test_with_credentials(self):
        adapter = DeltaMarketDataAdapter(api_key="key123", api_secret="secret456")
        assert adapter.api_key == "key123"
        assert adapter.api_secret == "secret456"


# ═══════════════════════════════════════════════════════════════════════════════
# Capabilities
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeltaCapabilities:
    def test_all_capabilities_reported(self):
        adapter = DeltaMarketDataAdapter()
        caps = adapter.supported_capabilities()

        assert "ohlcv" in caps
        assert "trades" in caps
        assert "funding" in caps
        assert "mark_price" in caps
        assert "open_interest" in caps
        assert "option_greeks" in caps
        assert "websocket" in caps

    def test_capability_count(self):
        adapter = DeltaMarketDataAdapter()
        assert len(adapter.supported_capabilities()) == 7


# ═══════════════════════════════════════════════════════════════════════════════
# Symbol Normalization
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeltaSymbolNormalization:
    def test_normalize_perpetual(self):
        adapter = DeltaMarketDataAdapter()
        assert adapter.normalize_symbol("BTCUSD") == "BTC"
        assert adapter.normalize_symbol("ETHUSD") == "ETH"
        assert adapter.normalize_symbol("SOLUSD") == "SOL"

    def test_normalize_option(self):
        adapter = DeltaMarketDataAdapter()
        assert adapter.normalize_symbol("C-BTC-65000-250627") == "BTC"
        assert adapter.normalize_symbol("P-ETH-4000-250328") == "ETH"

    def test_denormalize_perpetual(self):
        adapter = DeltaMarketDataAdapter()
        assert adapter.denormalize_symbol("BTC") == "BTCUSD"
        assert adapter.denormalize_symbol("ETH") == "ETHUSD"

    def test_denormalize_with_type(self):
        adapter = DeltaMarketDataAdapter()
        result = adapter.denormalize_symbol("BTC", InstrumentType.PERPETUAL)
        assert result == "BTCUSD"


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket Subscriptions
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeltaWebSocket:
    def test_subscription_payload(self):
        adapter = DeltaMarketDataAdapter()
        payloads = adapter.websocket_subscriptions(["BTCUSD"])

        assert len(payloads) == 1
        assert payloads[0]["type"] == "subscribe"

        channels = payloads[0]["payload"]["channels"]
        channel_names = [c["name"] for c in channels]

        assert "candlestick_1m" in channel_names
        assert "all_trades" in channel_names
        assert "funding_rate" in channel_names
        assert "mark_price" in channel_names

    def test_multi_symbol_subscriptions(self):
        adapter = DeltaMarketDataAdapter()
        payloads = adapter.websocket_subscriptions(["BTCUSD", "ETHUSD"])

        channels = payloads[0]["payload"]["channels"]
        # 4 channels per symbol × 2 symbols = 8
        assert len(channels) == 8


# ═══════════════════════════════════════════════════════════════════════════════
# Instrument Mapping
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeltaInstrumentMapping:
    def test_map_perpetual_product(self):
        adapter = DeltaMarketDataAdapter()
        product = {
            "symbol": "BTCUSD",
            "contract_type": "perpetual_futures",
            "contract_value": "0.001",
            "tick_size": "0.5",
            "lot_size": "1",
            "state": "live",
            "quoting_asset": {"symbol": "USD"},
            "settling_asset": {"symbol": "BTC"},
        }
        inst = adapter._map_product_to_instrument(product)

        assert inst is not None
        assert inst.exchange == "delta"
        assert inst.native_symbol == "BTCUSD"
        assert inst.canonical_symbol == "BTC"
        assert inst.instrument_type == InstrumentType.PERPETUAL
        assert inst.quote_asset == "USD"
        assert inst.settlement_asset == "BTC"
        assert inst.contract_size == 0.001
        assert inst.is_active is True

    def test_map_option_product(self):
        adapter = DeltaMarketDataAdapter()
        product = {
            "symbol": "C-BTC-65000-250627",
            "contract_type": "call_options",
            "strike_price": "65000",
            "settlement_time": "2025-06-27T08:00:00Z",
            "contract_value": "0.001",
            "tick_size": "0.5",
            "state": "live",
            "quoting_asset": {"symbol": "USD"},
            "settling_asset": {"symbol": "BTC"},
        }
        inst = adapter._map_product_to_instrument(product)

        assert inst is not None
        assert inst.instrument_type == InstrumentType.CALL_OPTION
        assert inst.strike == 65000.0
        assert inst.option_type is not None
        assert inst.expiry is not None

    def test_unknown_product_type_skipped(self):
        adapter = DeltaMarketDataAdapter()
        product = {
            "symbol": "WEIRD_PRODUCT",
            "contract_type": "totally_unknown_type",
        }
        inst = adapter._map_product_to_instrument(product)
        assert inst is None
