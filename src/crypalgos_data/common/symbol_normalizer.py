"""
Bidirectional symbol normalization engine.

Maps exchange-native symbols to a canonical form and back, enabling
cross-exchange queries (e.g. "get BTC candles from Delta *and* Binance").

The normalizer is populated at runtime from ``fetch_instruments()`` results
so it always reflects the actual products available on each exchange.

Examples
--------
>>> normalizer = SymbolNormalizer()
>>> normalizer.register_instrument(inst)   # inst.native_symbol="BTCUSD"
>>> normalizer.to_canonical("BTCUSD")
'BTC'
>>> normalizer.to_native("BTC", InstrumentType.PERPETUAL)
'BTCUSD'
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .market_data_models import Instrument, InstrumentType

logger = logging.getLogger(__name__)


class SymbolNormalizer:
    """
    Bidirectional symbol normalizer scoped to a single exchange.

    Each exchange adapter should hold its own ``SymbolNormalizer`` instance,
    populated via :meth:`build_from_instruments` after fetching the product
    catalogue.
    """

    def __init__(self, exchange_id: str = "") -> None:
        self.exchange_id = exchange_id

        # native_symbol → canonical_symbol  (e.g. "BTCUSD" → "BTC")
        self._native_to_canonical: Dict[str, str] = {}

        # (canonical_symbol, instrument_type) → native_symbol
        self._canonical_to_native: Dict[tuple[str, InstrumentType], str] = {}

        # canonical_symbol → list of native_symbols (all types)
        self._canonical_all: Dict[str, List[str]] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Registration
    # ──────────────────────────────────────────────────────────────────────────

    def register_instrument(self, instrument: Instrument) -> None:
        """Register a single instrument for bidirectional lookup."""
        native = instrument.native_symbol
        canonical = instrument.canonical_symbol
        itype = instrument.instrument_type

        self._native_to_canonical[native] = canonical
        self._canonical_to_native[(canonical, itype)] = native

        if canonical not in self._canonical_all:
            self._canonical_all[canonical] = []
        if native not in self._canonical_all[canonical]:
            self._canonical_all[canonical].append(native)

    def build_from_instruments(self, instruments: List[Instrument]) -> None:
        """Bulk-register a list of instruments (typically from ``fetch_instruments()``)."""
        self._native_to_canonical.clear()
        self._canonical_to_native.clear()
        self._canonical_all.clear()

        for inst in instruments:
            self.register_instrument(inst)

        logger.info(
            "[%s] SymbolNormalizer built: %d native symbols → %d canonical symbols",
            self.exchange_id,
            len(self._native_to_canonical),
            len(self._canonical_all),
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Forward: native → canonical
    # ──────────────────────────────────────────────────────────────────────────

    def to_canonical(self, native_symbol: str) -> Optional[str]:
        """
        Convert an exchange-native symbol to the canonical form.

        Returns ``None`` if the symbol has not been registered.
        """
        return self._native_to_canonical.get(native_symbol)

    # ──────────────────────────────────────────────────────────────────────────
    # Reverse: canonical → native
    # ──────────────────────────────────────────────────────────────────────────

    def to_native(
        self,
        canonical_symbol: str,
        instrument_type: InstrumentType = InstrumentType.PERPETUAL,
    ) -> Optional[str]:
        """
        Convert a canonical symbol back to the exchange-native symbol for
        the given instrument type.

        Returns ``None`` if no matching instrument has been registered.
        """
        return self._canonical_to_native.get((canonical_symbol, instrument_type))

    def all_native_symbols(self, canonical_symbol: str) -> List[str]:
        """Return all native symbols mapped to a canonical symbol (across all types)."""
        return list(self._canonical_all.get(canonical_symbol, []))

    # ──────────────────────────────────────────────────────────────────────────
    # Convenience
    # ──────────────────────────────────────────────────────────────────────────

    def list_canonical_symbols(self) -> List[str]:
        """Return all registered canonical symbols."""
        return sorted(self._canonical_all.keys())

    def list_native_symbols(self) -> List[str]:
        """Return all registered native symbols."""
        return sorted(self._native_to_canonical.keys())

    def __len__(self) -> int:
        return len(self._native_to_canonical)

    def __repr__(self) -> str:
        return (
            f"SymbolNormalizer(exchange={self.exchange_id!r}, "
            f"native={len(self._native_to_canonical)}, "
            f"canonical={len(self._canonical_all)})"
        )
