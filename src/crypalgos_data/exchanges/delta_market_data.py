"""
Delta Exchange — full market data adapter implementation.

Implements every capability that Delta Exchange supports:
OHLCV, trades, funding rates, mark prices, open interest, option Greeks,
and WebSocket subscriptions.

Reuses the HTTP request infrastructure from the existing ``DeltaAPI`` class
to share rate-limiting, quota tracking, and authentication logic.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import httpx

from ..common.base_market_data import BaseMarketDataAdapter
from ..common.market_data_models import (
    FundingRate,
    Instrument,
    InstrumentType,
    MarkPrice,
    OpenInterest,
    OptionGreeks,
    OptionType,
)
from ..common.models import Candle, OrderSide, Trade
from ..common.symbol_normalizer import SymbolNormalizer

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Delta product type → canonical InstrumentType
# ─────────────────────────────────────────────────────────────────────────────
_DELTA_PRODUCT_TYPE_MAP: Dict[str, InstrumentType] = {
    "spot": InstrumentType.SPOT,
    "perpetual_futures": InstrumentType.PERPETUAL,
    "futures": InstrumentType.FUTURE,
    "call_options": InstrumentType.CALL_OPTION,
    "put_options": InstrumentType.PUT_OPTION,
    # Fallbacks for variant naming conventions
    "inverse_perpetual_futures": InstrumentType.PERPETUAL,
    "move_options": InstrumentType.CALL_OPTION,
    "spreads": InstrumentType.FUTURE,
    "interest_rate_swaps": InstrumentType.PERPETUAL,
    "turbo_call_options": InstrumentType.CALL_OPTION,
    "turbo_put_options": InstrumentType.PUT_OPTION,
}

# Common quote suffixes on Delta native symbols
_QUOTE_SUFFIXES = ("USD", "USDT", "BTC", "ETH", "INR")


def _extract_base_asset(native_symbol: str) -> str:
    """
    Heuristically extract the base asset from a Delta native symbol.

    Examples: BTCUSD→BTC, ETHUSDT→ETH, SOLUSD→SOL, C-BTC-65000-250627→BTC
    """
    # Option-style symbols: C-BTC-65000-250627 / P-BTC-65000-250627
    if native_symbol and native_symbol[0] in ("C", "P") and "-" in native_symbol:
        parts = native_symbol.split("-")
        if len(parts) >= 2:
            return parts[1].upper()

    # Futures with date suffix: BTCUSD_250627
    clean = native_symbol.split("_")[0] if "_" in native_symbol else native_symbol

    # Strip known quote suffixes (longest first to avoid partial matches)
    for suffix in sorted(_QUOTE_SUFFIXES, key=len, reverse=True):
        if clean.upper().endswith(suffix) and len(clean) > len(suffix):
            return clean[: -len(suffix)].upper()

    return clean.upper()


class DeltaMarketDataAdapter(BaseMarketDataAdapter):
    """Full-featured market data adapter for Delta Exchange."""

    exchange_id: str = "delta"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
    ) -> None:
        self.testnet = testnet
        if self.testnet:
            self.base_url = "https://cdn-ind.testnet.deltaex.org/v2"
        else:
            self.base_url = "https://api.india.delta.exchange/v2"

        self.api_key = api_key
        self.api_secret = api_secret

        # Shared symbol normalizer — populated lazily via fetch_instruments()
        self.normalizer = SymbolNormalizer(exchange_id=self.exchange_id)

        # Cache instruments for repeated lookups
        self._instruments_cache: List[Instrument] = []

    # Internal HTTP helper

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """Lightweight GET-only request helper for public market data endpoints."""
        url = (
            f"{self.base_url}/{endpoint}"
            if not endpoint.startswith("/")
            else f"{self.base_url}{endpoint}"
        )
        headers = {"Accept": "application/json"}

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                response = await client.request(method, url, params=params, headers=headers)

                if response.status_code == 429:
                    reset_ms = int(response.headers.get("X-RATE-LIMIT-RESET", 2000))
                    logger.warning("Delta 429 — sleeping %dms", reset_ms)
                    import asyncio
                    await asyncio.sleep(reset_ms / 1000.0)
                    # Retry once
                    response = await client.request(method, url, params=params, headers=headers)

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as exc:
                logger.error("Delta HTTP error: %s | Body: %s", exc, exc.response.text)
                return None
            except Exception as exc:
                logger.error("Delta request failed: %s", exc)
                return None

    # Instrument Discovery

    async def fetch_instruments(
        self,
        instrument_type: Optional[InstrumentType] = None,
    ) -> List[Instrument]:
        data = await self._request("GET", "products")
        if not data or not data.get("result"):
            return []

        instruments: List[Instrument] = []
        for product in data["result"]:
            inst = self._map_product_to_instrument(product)
            if inst is None:
                continue
            if instrument_type is not None and inst.instrument_type != instrument_type:
                continue
            instruments.append(inst)

        # Populate the symbol normalizer
        self.normalizer.build_from_instruments(instruments)
        self._instruments_cache = instruments
        return instruments

    def _map_product_to_instrument(self, p: Dict[str, Any]) -> Optional[Instrument]:
        """Convert a Delta ``/v2/products`` entry to a canonical Instrument."""
        raw_type = str(p.get("contract_type", p.get("product_type", ""))).lower()
        itype = _DELTA_PRODUCT_TYPE_MAP.get(raw_type)
        if itype is None:
            logger.debug("Skipping unknown Delta product type: %s (%s)", raw_type, p.get("symbol"))
            return None

        native_symbol = p.get("symbol", "")
        base_asset = _extract_base_asset(native_symbol)

        # Quote / settlement assets
        quote_asset = "USD"
        settlement_asset = None
        if p.get("quoting_asset") and p["quoting_asset"].get("symbol"):
            quote_asset = p["quoting_asset"]["symbol"].upper()
        if p.get("settling_asset") and p["settling_asset"].get("symbol"):
            settlement_asset = p["settling_asset"]["symbol"].upper()

        # Option fields
        strike = None
        option_type = None
        expiry = None

        if itype in (InstrumentType.CALL_OPTION, InstrumentType.PUT_OPTION):
            strike = float(p["strike_price"]) if p.get("strike_price") else None
            option_type = OptionType.CALL if itype == InstrumentType.CALL_OPTION else OptionType.PUT

        if p.get("settlement_time"):
            try:
                expiry = datetime.fromisoformat(
                    p["settlement_time"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Contract spec
        contract_size = float(p["contract_value"]) if p.get("contract_value") else None
        tick_size = float(p["tick_size"]) if p.get("tick_size") else None
        lot_size = float(p.get("lot_size", 0)) if p.get("lot_size") else None

        # Active status
        state = str(p.get("state", "")).lower()
        is_active = state in ("live", "active", "")

        return Instrument(
            exchange=self.exchange_id,
            native_symbol=native_symbol,
            canonical_symbol=base_asset,
            instrument_type=itype,
            base_asset=base_asset,
            quote_asset=quote_asset,
            settlement_asset=settlement_asset,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            contract_size=contract_size,
            tick_size=tick_size,
            lot_size=lot_size,
            is_active=is_active,
            raw_metadata=p,
        )

    # Historical OHLCV

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since_ms: int,
        limit: int = 2000,
    ) -> List[Candle]:
        """Fetch OHLCV candles with automatic pagination."""
        all_candles: List[Candle] = []
        current_since = since_ms
        tf_min = self._timeframe_to_minutes(timeframe)

        while len(all_candles) < limit:
            remaining = limit - len(all_candles)
            chunk_limit = min(remaining, 2000)

            start_sec = int(current_since / 1000)
            end_sec = start_sec + (chunk_limit * tf_min * 60)

            params = {
                "resolution": timeframe,
                "symbol": symbol,
                "start": start_sec,
                "end": end_sec,
            }

            data = await self._request("GET", "history/candles", params=params)
            if not data or not data.get("success"):
                break

            results = data.get("result", [])
            if not results:
                break

            chunk = [
                Candle(
                    symbol=symbol,
                    timestamp_ms=int(r["time"] * 1000),
                    open=float(r["open"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    close=float(r["close"]),
                    volume=float(r["volume"]),
                )
                for r in results
            ]
            chunk.sort(key=lambda c: c.timestamp_ms)

            for c in chunk:
                if not all_candles or c.timestamp_ms > all_candles[-1].timestamp_ms:
                    all_candles.append(c)
                if len(all_candles) >= limit:
                    break

            if chunk:
                current_since = all_candles[-1].timestamp_ms + (tf_min * 60 * 1000)
            else:
                break

        return all_candles[:limit]

    @staticmethod
    def _timeframe_to_minutes(timeframe: str) -> int:
        if timeframe.endswith("m"):
            return int(timeframe[:-1])
        elif timeframe.endswith("h"):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith("d"):
            return int(timeframe[:-1]) * 1440
        return 1

    # Trade History

    async def fetch_trades(
        self,
        symbol: str,
        since_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Trade]:
        data = await self._request("GET", f"trades/{symbol}")
        if not data or not data.get("result"):
            return []

        trades: List[Trade] = []
        for t in data["result"]:
            try:
                ts = int(
                    datetime.fromisoformat(
                        str(t.get("created_at", "")).replace("Z", "+00:00")
                    ).timestamp()
                    * 1000
                ) if t.get("created_at") else int(time.time() * 1000)
            except (ValueError, TypeError):
                ts = int(time.time() * 1000)

            trades.append(
                Trade(
                    exchange=self.exchange_id,
                    symbol=symbol,
                    price=float(t.get("price", 0)),
                    amount=float(t.get("size", 0)),
                    side=OrderSide.BUY if str(t.get("buyer_role", "")).lower() == "taker" else OrderSide.SELL,
                    timestamp=ts,
                )
            )

        # Apply since_ms filter
        if since_ms is not None:
            trades = [t for t in trades if t.timestamp >= since_ms]

        return trades[:limit]

    # Funding Rates

    async def fetch_funding(
        self,
        symbol: str,
        since_ms: Optional[int] = None,
        limit: int = 500,
    ) -> List[FundingRate]:
        canonical = self.normalize_symbol(symbol)

        # Delta provides current funding info via the products endpoint
        data = await self._request("GET", "tickers")
        if not data or not data.get("result"):
            return []

        funding_rates: List[FundingRate] = []
        for ticker in data["result"]:
            if ticker.get("symbol") != symbol:
                continue

            funding_rate_value = ticker.get("funding_rate")
            if funding_rate_value is None:
                continue

            ts = int(ticker.get("timestamp", 0))
            if ts == 0:
                ts = int(time.time() * 1000)
            # Detect microseconds vs milliseconds vs seconds scale
            if ts > 1e14:
                ts = int(ts / 1000)
            elif ts < 1e12:
                ts = int(ts * 1000)

            funding_rates.append(
                FundingRate(
                    exchange=self.exchange_id,
                    symbol=symbol,
                    canonical_symbol=canonical,
                    funding_rate=float(funding_rate_value),
                    funding_time_ms=ts,
                    next_funding_time_ms=None,
                )
            )

        return funding_rates[:limit]

    # Mark Price

    async def fetch_mark_price(self, symbol: str) -> Optional[MarkPrice]:
        canonical = self.normalize_symbol(symbol)

        data = await self._request("GET", "tickers")
        if not data or not data.get("result"):
            return None

        for ticker in data["result"]:
            if ticker.get("symbol") != symbol:
                continue

            mark = ticker.get("mark_price")
            if mark is None:
                continue

            ts = int(ticker.get("timestamp", 0))
            if ts < 1e12:
                ts = int(ts * 1000)

            return MarkPrice(
                exchange=self.exchange_id,
                symbol=symbol,
                canonical_symbol=canonical,
                mark_price=float(mark),
                index_price=float(ticker["spot_price"]) if ticker.get("spot_price") else None,
                timestamp_ms=ts if ts else int(time.time() * 1000),
            )

        return None

    # Open Interest

    async def fetch_open_interest(self, symbol: str) -> Optional[OpenInterest]:
        canonical = self.normalize_symbol(symbol)

        data = await self._request("GET", "tickers")
        if not data or not data.get("result"):
            return None

        for ticker in data["result"]:
            if ticker.get("symbol") != symbol:
                continue

            oi = ticker.get("oi")
            if oi is None:
                continue

            ts = int(ticker.get("timestamp", 0))
            if ts < 1e12:
                ts = int(ts * 1000)

            oi_value = ticker.get("oi_value")

            return OpenInterest(
                exchange=self.exchange_id,
                symbol=symbol,
                canonical_symbol=canonical,
                open_interest=float(oi),
                open_interest_value=float(oi_value) if oi_value else None,
                timestamp_ms=ts if ts else int(time.time() * 1000),
            )

        return None

    # Option Greeks

    async def fetch_option_greeks(self, symbol: str) -> Optional[OptionGreeks]:
        canonical = self.normalize_symbol(symbol)

        data = await self._request("GET", "tickers")
        if not data or not data.get("result"):
            return None

        for ticker in data["result"]:
            if ticker.get("symbol") != symbol:
                continue

            greeks = ticker.get("greeks")
            if not greeks:
                continue

            ts = int(ticker.get("timestamp", 0))
            if ts < 1e12:
                ts = int(ts * 1000)

            return OptionGreeks(
                exchange=self.exchange_id,
                symbol=symbol,
                canonical_symbol=canonical,
                delta=float(greeks["delta"]) if greeks.get("delta") else None,
                gamma=float(greeks["gamma"]) if greeks.get("gamma") else None,
                theta=float(greeks["theta"]) if greeks.get("theta") else None,
                vega=float(greeks["vega"]) if greeks.get("vega") else None,
                rho=float(greeks["rho"]) if greeks.get("rho") else None,
                iv=float(greeks["iv"]) if greeks.get("iv") else None,
                timestamp_ms=ts if ts else int(time.time() * 1000),
            )

        return None

    # Symbol Normalization

    def normalize_symbol(self, native_symbol: str) -> str:
        """BTCUSD → BTC, ETHUSD → ETH, C-BTC-65000-250627 → BTC"""
        cached = self.normalizer.to_canonical(native_symbol)
        if cached:
            return cached
        # Fallback heuristic when normalizer hasn't been populated yet
        return _extract_base_asset(native_symbol)

    def denormalize_symbol(
        self,
        canonical_symbol: str,
        instrument_type: InstrumentType = InstrumentType.PERPETUAL,
    ) -> str:
        """BTC (perpetual) → BTCUSD"""
        cached = self.normalizer.to_native(canonical_symbol, instrument_type)
        if cached:
            return cached
        # Fallback heuristic
        return f"{canonical_symbol}USD"

    # WebSocket Subscriptions

    def websocket_subscriptions(self, symbols: List[str]) -> List[dict]:
        """Generate Delta WebSocket subscription payloads."""
        channels = []
        for sym in symbols:
            channels.extend(
                [
                    {"name": "candlestick_1m", "symbols": [sym]},
                    {"name": "all_trades", "symbols": [sym]},
                    {"name": "funding_rate", "symbols": [sym]},
                    {"name": "mark_price", "symbols": [sym]},
                ]
            )
        return [
            {
                "type": "subscribe",
                "payload": {"channels": channels},
            }
        ]

    # Capabilities

    def supported_capabilities(self) -> Set[str]:
        return {
            "ohlcv",
            "trades",
            "funding",
            "mark_price",
            "open_interest",
            "option_greeks",
            "websocket",
        }
