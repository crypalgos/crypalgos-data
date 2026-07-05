"""
Tests for the bidirectional symbol normalizer.
"""

import pytest
from crypalgos_data.common.symbol_normalizer import SymbolNormalizer
from crypalgos_data.common.market_data_models import Instrument, InstrumentType


def _make_instrument(
    exchange: str,
    native: str,
    canonical: str,
    itype: InstrumentType = InstrumentType.PERPETUAL,
) -> Instrument:
    return Instrument(
        exchange=exchange,
        native_symbol=native,
        canonical_symbol=canonical,
        instrument_type=itype,
        base_asset=canonical,
        quote_asset="USD",
    )


class TestSymbolNormalizer:
    def test_register_and_lookup(self):
        norm = SymbolNormalizer(exchange_id="delta")
        inst = _make_instrument("delta", "BTCUSD", "BTC")
        norm.register_instrument(inst)

        assert norm.to_canonical("BTCUSD") == "BTC"
        assert norm.to_native("BTC", InstrumentType.PERPETUAL) == "BTCUSD"

    def test_build_from_instruments(self):
        norm = SymbolNormalizer(exchange_id="delta")
        instruments = [
            _make_instrument("delta", "BTCUSD", "BTC"),
            _make_instrument("delta", "ETHUSD", "ETH"),
            _make_instrument("delta", "SOLUSD", "SOL"),
        ]
        norm.build_from_instruments(instruments)

        assert norm.to_canonical("BTCUSD") == "BTC"
        assert norm.to_canonical("ETHUSD") == "ETH"
        assert norm.to_canonical("SOLUSD") == "SOL"
        assert len(norm) == 3

    def test_unknown_symbol_returns_none(self):
        norm = SymbolNormalizer(exchange_id="delta")
        assert norm.to_canonical("UNKNOWN") is None
        assert norm.to_native("UNKNOWN", InstrumentType.PERPETUAL) is None

    def test_multiple_instrument_types(self):
        norm = SymbolNormalizer(exchange_id="delta")
        instruments = [
            _make_instrument("delta", "BTCUSD", "BTC", InstrumentType.PERPETUAL),
            _make_instrument("delta", "BTCUSD_SPOT", "BTC", InstrumentType.SPOT),
        ]
        norm.build_from_instruments(instruments)

        assert norm.to_native("BTC", InstrumentType.PERPETUAL) == "BTCUSD"
        assert norm.to_native("BTC", InstrumentType.SPOT) == "BTCUSD_SPOT"

    def test_all_native_symbols(self):
        norm = SymbolNormalizer(exchange_id="delta")
        instruments = [
            _make_instrument("delta", "BTCUSD", "BTC", InstrumentType.PERPETUAL),
            _make_instrument("delta", "BTCUSD_250627", "BTC", InstrumentType.FUTURE),
        ]
        norm.build_from_instruments(instruments)

        all_native = norm.all_native_symbols("BTC")
        assert "BTCUSD" in all_native
        assert "BTCUSD_250627" in all_native

    def test_list_methods(self):
        norm = SymbolNormalizer(exchange_id="delta")
        instruments = [
            _make_instrument("delta", "BTCUSD", "BTC"),
            _make_instrument("delta", "ETHUSD", "ETH"),
        ]
        norm.build_from_instruments(instruments)

        assert norm.list_canonical_symbols() == ["BTC", "ETH"]
        assert norm.list_native_symbols() == ["BTCUSD", "ETHUSD"]

    def test_rebuild_clears_old_data(self):
        norm = SymbolNormalizer(exchange_id="delta")
        norm.build_from_instruments([
            _make_instrument("delta", "BTCUSD", "BTC"),
        ])
        assert norm.to_canonical("BTCUSD") == "BTC"

        # Rebuild with different data
        norm.build_from_instruments([
            _make_instrument("delta", "ETHUSD", "ETH"),
        ])
        assert norm.to_canonical("BTCUSD") is None  # Cleared
        assert norm.to_canonical("ETHUSD") == "ETH"

    def test_repr(self):
        norm = SymbolNormalizer(exchange_id="delta")
        norm.build_from_instruments([
            _make_instrument("delta", "BTCUSD", "BTC"),
        ])
        r = repr(norm)
        assert "delta" in r
        assert "native=1" in r
        assert "canonical=1" in r


class TestBinanceNormalization:
    """Test Binance-style symbol conventions."""

    def test_binance_symbols(self):
        norm = SymbolNormalizer(exchange_id="binance")
        instruments = [
            _make_instrument("binance", "BTCUSDT", "BTC"),
            _make_instrument("binance", "ETHUSDT", "ETH"),
            _make_instrument("binance", "SOLUSDT", "SOL"),
        ]
        norm.build_from_instruments(instruments)

        assert norm.to_canonical("BTCUSDT") == "BTC"
        assert norm.to_native("BTC", InstrumentType.PERPETUAL) == "BTCUSDT"


class TestCoinDCXNormalization:
    """Test CoinDCX-style symbol conventions."""

    def test_coindcx_symbols(self):
        norm = SymbolNormalizer(exchange_id="coindcx")
        instruments = [
            _make_instrument("coindcx", "BTCINR", "BTC", InstrumentType.SPOT),
            _make_instrument("coindcx", "ETHINR", "ETH", InstrumentType.SPOT),
        ]
        norm.build_from_instruments(instruments)

        assert norm.to_canonical("BTCINR") == "BTC"
        assert norm.to_native("BTC", InstrumentType.SPOT) == "BTCINR"


# ── Phase 4 (T-DRY-4): static symbol string canonicalization ──────────────

def test_normalize_symbol_string():
    from crypalgos_data.common.symbol_normalizer import normalize_symbol_string

    assert normalize_symbol_string("btc/usdt") == "BTCUSD"
    assert normalize_symbol_string("BTC/USDT") == "BTCUSD"
    assert normalize_symbol_string("ethusd") == "ETHUSD"
    assert normalize_symbol_string(" SOLUSD ") == "SOLUSD"
    # Options symbols keep their dashes (used for asset-class detection)
    assert normalize_symbol_string("BTC-27MAY26-62000-C") == "BTC-27MAY26-62000-C"
