"""
Canonical market data models - exchange-agnostic, normalized representations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class InstrumentType(str, Enum):
    """Canonical instrument classification across all exchanges."""
    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURE = "future"
    CALL_OPTION = "call_option"
    PUT_OPTION = "put_option"


class OptionType(str, Enum):
    """Option flavor (call or put)."""
    CALL = "call"
    PUT = "put"


class Instrument(BaseModel):
    """Canonical normalized instrument descriptor."""

    exchange: str = Field(..., description="Exchange identifier (e.g. 'delta')")
    native_symbol: str = Field(..., description="Exchange native symbol (e.g. 'BTCUSD')")
    canonical_symbol: str = Field(..., description="Canonical base asset ticker (e.g. 'BTC')")
    instrument_type: InstrumentType
    base_asset: str
    quote_asset: str
    settlement_asset: Optional[str] = None

    # Derivatives fields
    expiry: Optional[datetime] = None
    strike: Optional[float] = None
    option_type: Optional[OptionType] = None

    # Contract specifications
    contract_size: Optional[float] = None
    tick_size: Optional[float] = None
    lot_size: Optional[float] = None

    is_active: bool = True
    raw_metadata: Optional[Dict[str, Any]] = None


class FundingRate(BaseModel):
    """Funding rate snapshot for perpetual contracts."""

    exchange: str
    symbol: str
    canonical_symbol: str
    funding_rate: float
    funding_time_ms: int
    next_funding_time_ms: Optional[int] = None


class MarkPrice(BaseModel):
    """Mark price and optional index price for derivatives."""

    exchange: str
    symbol: str
    canonical_symbol: str
    mark_price: float
    index_price: Optional[float] = None
    timestamp_ms: int


class OpenInterest(BaseModel):
    """Open interest for derivatives instruments."""

    exchange: str
    symbol: str
    canonical_symbol: str
    open_interest: float
    open_interest_value: Optional[float] = None
    timestamp_ms: int


class OptionGreeks(BaseModel):
    """Greeks snapshot for an options instrument."""

    exchange: str
    symbol: str
    canonical_symbol: str
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    iv: Optional[float] = None
    timestamp_ms: int
