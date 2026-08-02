import asyncio
import datetime
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _timestamp_to_milliseconds(timestamp: Any) -> Optional[int]:
    """Normalize Delta seconds/ms/microseconds/nanoseconds timestamps to ms."""
    try:
        value = int(float(timestamp))
    except (TypeError, ValueError):
        return None
    if value >= 1_000_000_000_000_000_000:
        return value // 1_000_000
    if value >= 1_000_000_000_000_000:
        return value // 1_000
    if value < 1_000_000_000_000:
        return value * 1_000
    return value


from ...common.base_stream import BaseExchangeClient
from ...common.market_data_models import MarkPrice, OpenInterest, OptionGreeks
from ...common.models import (
    Balance,
    Candle,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Ticker,
    Trade,
)
from ...exchanges.delta_market_data import _extract_base_asset


class DeltaExchangeClient(BaseExchangeClient):
    def __init__(self, broker, symbols=[], api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False):
        if testnet:
            URL = "wss://socket-ind.testnet.deltaex.org"
        else:
            URL = "wss://socket.india.delta.exchange"
        super().__init__(broker, "delta", URL)
        self.symbols = symbols
        self.api_key = api_key
        self.api_secret = api_secret

    async def after_connect(self):
        """Authenticates the WebSocket connection if keys are provided."""
        if not self.api_key or not self.api_secret:
            return

        timestamp = str(int(time.time()))
        method = "GET"
        path = "/live"
        
        # Delta Signature for WS: method + timestamp + path
        message = method + timestamp + path
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        auth_payload = {
            "type": "key-auth",
            "payload": {
                "api-key": self.api_key,
                "signature": signature,
                "timestamp": timestamp
            }
        }
        await self.ws.send(json.dumps(auth_payload))
        
        # Wait for auth confirmation
        try:
            auth_response = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
            auth_data = json.loads(auth_response)
            if auth_data.get("type") == "key-auth" and auth_data.get("success"):
                logger.info("Delta WebSocket Authentication SUCCESSful.")
            elif auth_data.get("type") == "error":
                logger.error(f"Delta WebSocket Authentication FAILED: {auth_data}")
            else:
                # Some versions might return type: success or Authenticated message
                logger.info(f"Delta WebSocket Auth Response: {auth_data}")
        except asyncio.TimeoutError:
            logger.error("Delta WebSocket Authentication timed out.")
        except Exception as e:
            logger.error(f"Error during WebSocket Authentication: {e}")

    def get_subscription_payload(self) -> dict:
        channels = [
            {"name": "all_trades", "symbols": self.symbols},
            {"name": "candlestick_1m", "symbols": self.symbols},
            {"name": "v2/ticker", "symbols": self.symbols}
        ]
        
        # Add private channels if authenticated
        if self.api_key:
            channels.extend([
                {"name": "orders", "symbols": ["all"]},
                {"name": "positions", "symbols": ["all"]},
                {"name": "user_fills", "symbols": ["all"]}
            ])
            
        return {
            "type": "subscribe",
            "payload": {
                "channels": channels
            }
        }

    def normalize_message(self, message: dict):
        msg_type = message.get("type")
        
        # Public Channels
        if msg_type == "all_trades":
            symbol = message.get("symbol", "")
            timestamp_ms = _timestamp_to_milliseconds(message.get("timestamp"))
            if message.get("price") is None or message.get("size") is None or timestamp_ms is None:
                return None
            return (
                "trade",
                Trade(
                    exchange="delta",
                    symbol=symbol,
                    price=float(message["price"]),
                    amount=float(message["size"]),
                    timestamp=timestamp_ms,
                    side=OrderSide.SELL if message.get("buyer_role") == "maker" else OrderSide.BUY,
                ),
            )
        
        if msg_type == "candlestick_1m":
            if message.get("open") is None or message.get("close") is None:
                return None
            symbol = message.get("symbol", "")
            timestamp_ms = _timestamp_to_milliseconds(
                message.get("candle_start_time") or message.get("timestamp")
            )
            if timestamp_ms is None:
                return None
            # Align the canonical candle start to the 1-minute boundary.
            ts_ms = timestamp_ms - (timestamp_ms % 60_000)
            return ("ohlcv", Candle(
                symbol=symbol,
                timestamp_ms=ts_ms,
                open=float(message.get("open")),
                high=float(message.get("high")),
                low=float(message.get("low")),
                close=float(message.get("close")),
                volume=float(message.get("volume"))
            ))

        if msg_type == "v2/ticker":
            quotes = message.get("quotes") or {}
            symbol = message.get("symbol", "")
            timestamp_ms = _timestamp_to_milliseconds(message.get("timestamp"))
            # Delta's public ticker has used both nested quotes/close and the
            # current best_bid/best_ask/last_price representation. Support
            # both without ever using mark_price as an executable-price proxy.
            try:
                last = float(message.get("last_price", message.get("close", 0)) or 0)
                ticker = Ticker(
                    exchange="delta",
                    symbol=symbol,
                    bid=float(quotes.get("best_bid", message.get("best_bid", 0)) or 0),
                    ask=float(quotes.get("best_ask", message.get("best_ask", 0)) or 0),
                    last=last,
                    mark_price=float(message.get("mark_price") or 0),
                    volume_24h=float(message.get("volume_24h", message.get("volume", 0)) or 0),
                    timestamp=timestamp_ms or 0,
                )
            except (TypeError, ValueError):
                return None
            if not symbol or timestamp_ms is None or last <= 0:
                return None
            updates = [("ticker", ticker)]

            greeks_raw = message.get("greeks")
            if greeks_raw:
                base = _extract_base_asset(symbol)
                greeks = OptionGreeks(
                    exchange="delta",
                    symbol=symbol,
                    canonical_symbol=base,
                    delta=float(greeks_raw.get("delta")) if greeks_raw.get("delta") else None,
                    gamma=float(greeks_raw.get("gamma")) if greeks_raw.get("gamma") else None,
                    theta=float(greeks_raw.get("theta")) if greeks_raw.get("theta") else None,
                    vega=float(greeks_raw.get("vega")) if greeks_raw.get("vega") else None,
                    rho=float(greeks_raw.get("rho")) if greeks_raw.get("rho") else None,
                    iv=float(greeks_raw.get("iv")) if greeks_raw.get("iv") else None,
                    timestamp_ms=timestamp_ms,
                )
                updates.append(("option_greeks", greeks))

            mp_val = message.get("mark_price")
            if mp_val is not None:
                base = _extract_base_asset(symbol)
                mark_price = MarkPrice(
                    exchange="delta",
                    symbol=symbol,
                    canonical_symbol=base,
                    mark_price=float(mp_val),
                    index_price=float(message.get("spot_price")) if message.get("spot_price") else None,
                    timestamp_ms=timestamp_ms,
                )
                updates.append(("mark_price", mark_price))

            oi_val = message.get("oi")
            if oi_val is not None:
                base = _extract_base_asset(symbol)
                oi_desc = OpenInterest(
                    exchange="delta",
                    symbol=symbol,
                    canonical_symbol=base,
                    open_interest=float(oi_val),
                    open_interest_value=float(message.get("oi_value")) if message.get("oi_value") else None,
                    timestamp_ms=timestamp_ms,
                )
                updates.append(("open_interest", oi_desc))

            return updates

        # Private Channels
        if msg_type == "orders":
            return ("order", self._map_order(message))
            
        if msg_type == "positions":
            return ("position", Position(
                exchange="delta",
                symbol=message.get("symbol", message.get("product_symbol", "unknown")),
                size=float(message.get("size") or 0),
                entry_price=float(message.get("entry_price") or 0),
                mark_price=float(message.get("mark_price") or 0),
                unrealized_pnl=float(message.get("unrealized_pnl") or 0),
                margin=float(message.get("margin") or 0),
                timestamp=int(time.time() * 1000)
            ))
            
        if msg_type == "user_balances":
            return ("balance", Balance(
                exchange="delta",
                asset=message.get("asset_symbol", "unknown"),
                total=float(message.get("balance") or 0),
                available=float(message.get("available_balance") or 0),
                blocked=float(message.get("balance", 0)) - float(message.get("available_balance", 0)),
                timestamp=int(time.time() * 1000)
            ))
            
        return None

    def _map_order(self, r: dict) -> Order:
        """Maps Delta order WS message to normalized Order model."""
        side_raw = r.get("side", "buy")
        side = OrderSide.BUY if side_raw == "buy" else OrderSide.SELL
        
        # Map type
        type_map = {
            "limit_order": OrderType.LIMIT,
            "market_order": OrderType.MARKET,
            "stop_loss_limit": OrderType.STOP_LOSS_LIMIT,
            "stop_loss_market": OrderType.STOP_LOSS_MARKET,
            "take_profit_limit": OrderType.TAKE_PROFIT_LIMIT,
            "take_profit_market": OrderType.TAKE_PROFIT_MARKET
        }
        o_type = type_map.get(r.get("order_type"), OrderType.LIMIT)
        
        status_map = {
            "open": OrderStatus.OPEN,
            "closed": OrderStatus.CLOSED,
            "cancelled": OrderStatus.CANCELED,
            "pending": OrderStatus.PENDING,
            "rejected": OrderStatus.REJECTED
        }
        status = status_map.get(r.get("state"), OrderStatus.OPEN)
        
        return Order(
            id=str(r.get("id", "0")),
            exchange="delta",
            symbol=r.get("product_symbol", r.get("symbol", "unknown")),
            side=side,
            type=o_type,
            size=float(r.get("size", 0)),
            price=float(r["limit_price"]) if r.get("limit_price") else None,
            stop_price=float(r["stop_price"]) if r.get("stop_price") else None,
            status=status,
            filled_size=float(r.get("filled_size", 0)),
            average_price=float(r["average_fill_price"]) if r.get("average_fill_price") else None,
            tp_price=(
                float(r["bracket_take_profit_price"]) if r.get("bracket_take_profit_price") else 
                float(r["take_profit_order"]["stop_price"]) if r.get("take_profit_order") and r["take_profit_order"].get("stop_price") else 
                None
            ),
            sl_price=(
                float(r["bracket_stop_loss_price"]) if r.get("bracket_stop_loss_price") else 
                float(r["stop_loss_order"]["stop_price"]) if r.get("stop_loss_order") and r["stop_loss_order"].get("stop_price") else 
                None
            ),
            timestamp=int(
                datetime.datetime.fromisoformat(r["updated_at"].replace('Z', '+00:00')).timestamp() * 1000
                if isinstance(r.get("updated_at"), str) and "T" in r.get("updated_at")
                else int(r.get("updated_at", time.time() * 1000000)) / 1000
            )
        )
