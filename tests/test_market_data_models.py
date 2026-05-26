"""
Tests for canonical market data models.
"""

import pytest
from datetime import datetime, timezone
from crypalgos_data.common.market_data_models import (
    Instrument,
    InstrumentType,
    OptionType,
    FundingRate,
    MarkPrice,
    OpenInterest,
    OptionGreeks,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Instrument Model Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestInstrument:
    def test_perpetual_instrument(self):
        inst = Instrument(
            exchange="delta",
            native_symbol="BTCUSD",
            canonical_symbol="BTC",
            instrument_type=InstrumentType.PERPETUAL,
            base_asset="BTC",
            quote_asset="USD",
            settlement_asset="BTC",
            contract_size=0.001,
            tick_size=0.5,
            lot_size=1.0,
        )
        assert inst.exchange == "delta"
        assert inst.native_symbol == "BTCUSD"
        assert inst.canonical_symbol == "BTC"
        assert inst.instrument_type == InstrumentType.PERPETUAL
        assert inst.expiry is None
        assert inst.strike is None
        assert inst.option_type is None
        assert inst.is_active is True

    def test_spot_instrument(self):
        inst = Instrument(
            exchange="binance",
            native_symbol="BTCUSDT",
            canonical_symbol="BTC",
            instrument_type=InstrumentType.SPOT,
            base_asset="BTC",
            quote_asset="USDT",
        )
        assert inst.instrument_type == InstrumentType.SPOT
        assert inst.settlement_asset is None

    def test_option_instrument(self):
        inst = Instrument(
            exchange="delta",
            native_symbol="C-BTC-65000-250627",
            canonical_symbol="BTC",
            instrument_type=InstrumentType.CALL_OPTION,
            base_asset="BTC",
            quote_asset="USD",
            strike=65000.0,
            option_type=OptionType.CALL,
            expiry=datetime(2025, 6, 27, tzinfo=timezone.utc),
        )
        assert inst.instrument_type == InstrumentType.CALL_OPTION
        assert inst.strike == 65000.0
        assert inst.option_type == OptionType.CALL
        assert inst.expiry is not None

    def test_future_instrument(self):
        inst = Instrument(
            exchange="delta",
            native_symbol="BTCUSD_250627",
            canonical_symbol="BTC",
            instrument_type=InstrumentType.FUTURE,
            base_asset="BTC",
            quote_asset="USD",
            expiry=datetime(2025, 6, 27, tzinfo=timezone.utc),
        )
        assert inst.instrument_type == InstrumentType.FUTURE
        assert inst.expiry is not None
        assert inst.strike is None

    def test_raw_metadata_stored(self):
        raw = {"id": 123, "symbol": "BTCUSD", "product_type": "perpetual_futures"}
        inst = Instrument(
            exchange="delta",
            native_symbol="BTCUSD",
            canonical_symbol="BTC",
            instrument_type=InstrumentType.PERPETUAL,
            base_asset="BTC",
            quote_asset="USD",
            raw_metadata=raw,
        )
        assert inst.raw_metadata == raw
        assert inst.raw_metadata["id"] == 123

    def test_instrument_serialization(self):
        inst = Instrument(
            exchange="delta",
            native_symbol="BTCUSD",
            canonical_symbol="BTC",
            instrument_type=InstrumentType.PERPETUAL,
            base_asset="BTC",
            quote_asset="USD",
        )
        d = inst.model_dump()
        assert d["exchange"] == "delta"
        assert d["instrument_type"] == "perpetual"

        # Round-trip
        inst2 = Instrument(**d)
        assert inst2 == inst


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnums:
    def test_instrument_type_values(self):
        assert InstrumentType.SPOT.value == "spot"
        assert InstrumentType.PERPETUAL.value == "perpetual"
        assert InstrumentType.FUTURE.value == "future"
        assert InstrumentType.CALL_OPTION.value == "call_option"
        assert InstrumentType.PUT_OPTION.value == "put_option"

    def test_option_type_values(self):
        assert OptionType.CALL.value == "call"
        assert OptionType.PUT.value == "put"


# ═══════════════════════════════════════════════════════════════════════════════
# FundingRate Model Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestFundingRate:
    def test_basic_funding_rate(self):
        fr = FundingRate(
            exchange="delta",
            symbol="BTCUSD",
            canonical_symbol="BTC",
            funding_rate=0.0001,
            funding_time_ms=1700000000000,
        )
        assert fr.funding_rate == 0.0001
        assert fr.next_funding_time_ms is None

    def test_funding_rate_with_next(self):
        fr = FundingRate(
            exchange="binance",
            symbol="BTCUSDT",
            canonical_symbol="BTC",
            funding_rate=-0.00005,
            funding_time_ms=1700000000000,
            next_funding_time_ms=1700028800000,
        )
        assert fr.funding_rate == -0.00005
        assert fr.next_funding_time_ms == 1700028800000


# ═══════════════════════════════════════════════════════════════════════════════
# MarkPrice Model Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarkPrice:
    def test_mark_price(self):
        mp = MarkPrice(
            exchange="delta",
            symbol="BTCUSD",
            canonical_symbol="BTC",
            mark_price=67500.5,
            index_price=67495.0,
            timestamp_ms=1700000000000,
        )
        assert mp.mark_price == 67500.5
        assert mp.index_price == 67495.0

    def test_mark_price_without_index(self):
        mp = MarkPrice(
            exchange="delta",
            symbol="BTCUSD",
            canonical_symbol="BTC",
            mark_price=67500.5,
            timestamp_ms=1700000000000,
        )
        assert mp.index_price is None


# ═══════════════════════════════════════════════════════════════════════════════
# OpenInterest Model Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestOpenInterest:
    def test_open_interest(self):
        oi = OpenInterest(
            exchange="delta",
            symbol="BTCUSD",
            canonical_symbol="BTC",
            open_interest=15000.0,
            open_interest_value=1012500000.0,
            timestamp_ms=1700000000000,
        )
        assert oi.open_interest == 15000.0
        assert oi.open_interest_value == 1012500000.0


# ═══════════════════════════════════════════════════════════════════════════════
# OptionGreeks Model Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestOptionGreeks:
    def test_full_greeks(self):
        g = OptionGreeks(
            exchange="delta",
            symbol="C-BTC-65000-250627",
            canonical_symbol="BTC",
            delta=0.55,
            gamma=0.001,
            theta=-5.2,
            vega=15.3,
            rho=0.02,
            iv=0.65,
            timestamp_ms=1700000000000,
        )
        assert g.delta == 0.55
        assert g.iv == 0.65

    def test_partial_greeks(self):
        g = OptionGreeks(
            exchange="delta",
            symbol="C-BTC-65000-250627",
            canonical_symbol="BTC",
            delta=0.55,
            timestamp_ms=1700000000000,
        )
        assert g.delta == 0.55
        assert g.gamma is None
        assert g.theta is None
        assert g.vega is None
