import httpx
import logging
import hmac
import hashlib
import asyncio
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..common.base_api import BaseExchangeAPI
from ..common.models import Candle, Ticker, Order, Position, Balance, OrderSide, OrderType, OrderStatus

logger = logging.getLogger(__name__)

class DeltaAPI(BaseExchangeAPI):
    # Quota Constants
    QUOTA_LIMIT = 10000
    WINDOW_SEC = 300  # 5 minutes
    
    # Weight Constants
    WEIGHTS = {
        "history/candles": 3,
        "products": 3,
        "tickers": 3,
        "orders": 5,
        "fills": 10,
        "history/orders": 10,
        "batch": 25
    }

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False):
        super().__init__()
        self.testnet = testnet
        if self.testnet:
            self.base_url = "https://cdn-ind.testnet.deltaex.org/v2"
        else:
            self.base_url = "https://api.india.delta.exchange/v2"
        
        self._rate_limit_ms = 50
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Quota tracking
        self._quota_used = 0
        self._window_start = time.time()
        self._lock = asyncio.Lock()
        
    def _generate_signature(self, method: str, path: str, query_string: str = "", payload: str = "") -> str:
        """Generates HMAC-SHA256 signature for Delta Exchange."""
        if not self.api_secret:
            return None, None
        
        timestamp = str(int(time.time()))
        
        # Delta Signature: method + timestamp + path + query_string + payload
            
        # Delta Signature: method + timestamp + path + query_string + payload
        message = method + timestamp + path + query_string + payload
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature, timestamp
        
    @property
    def rate_limit_ms(self) -> int:
        return self._rate_limit_ms

    def _get_weight(self, endpoint: str) -> int:
        """Returns the weight of an endpoint."""
        for path, weight in self.WEIGHTS.items():
            if path in endpoint:
                return weight
        return 1  # Default weight

    async def _check_quota(self, weight: int):
        """Ensures enough quota is available or sleeps until reset."""
        async with self._lock:
            now = time.time()
            # Reset window if 5 mins passed
            if now - self._window_start >= self.WINDOW_SEC:
                self._quota_used = 0
                self._window_start = now
                logger.debug("Delta API Quota window reset")

            if self._quota_used + weight > self.QUOTA_LIMIT:
                wait_time = self.WINDOW_SEC - (now - self._window_start)
                logger.warning(f"Delta API Quota exceeded. Waiting {wait_time:.2f}s for reset.")
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                # Reset and continue
                self._quota_used = weight
                self._window_start = time.time()
            else:
                self._quota_used += weight

    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_data: Optional[Dict] = None, auth: bool = False) -> Optional[Dict[str, Any]]:
        """Centralized async request helper with rate limiting and 429 handling."""
        weight = self._get_weight(endpoint)
        await self._check_quota(weight)

        path = f"/v2/{endpoint}" if not endpoint.startswith("/") else endpoint
        url = f"{self.base_url}{endpoint}" if endpoint.startswith("/") else f"{self.base_url}/{endpoint}"
        
        headers = {"Accept": "application/json"}
        payload = json.dumps(json_data, separators=(',', ':')) if json_data else ""
        
        if auth and self.api_key and self.api_secret:
            query_string = ""
            if params:
                query_string = "?" + "&".join([f"{k}={v}" for k, v in params.items()])
            
            signature, timestamp = self._generate_signature(method, path, query_string, payload)
            
            headers.update({
                "api-key": self.api_key,
                "signature": signature,
                "timestamp": timestamp,
                "Content-Type": "application/json"
            })

        async with httpx.AsyncClient(timeout=10) as client:
            while True:
                try:
                    # Use pre-serialized compact payload for consistency with signature
                    response = await client.request(method, url, params=params, content=payload, headers=headers)
                    
                    if response.status_code == 429:
                        reset_ms = int(response.headers.get('X-RATE-LIMIT-RESET', 1000))
                        logger.warning(f"Delta API 429 received. Sleeping for {reset_ms}ms (header).")
                        await asyncio.sleep(reset_ms / 1000.0)
                        continue
                    
                    response.raise_for_status()
                    resp_json = response.json()
                    logger.debug(f"Delta API Response [{method} {endpoint}]: {json.dumps(resp_json)}")
                    return resp_json

                except httpx.HTTPStatusError as e:
                    logger.error(f"Delta API HTTP error: {e} | Body: {response.text}")
                    return None
                except Exception as e:
                    logger.error(f"Delta API request failed: {e}")
                    return None

    async def fetch_products(self) -> List[Dict]:
        """Fetches all products."""
        data = await self._request("GET", "products")
        return data.get("result", []) if data else []

    async def fetch_l2_orderbook(self, symbol: str) -> Optional[Dict]:
        """Fetches L2 orderbook for a symbol (Public)."""
        data = await self._request("GET", f"l2-orderbook/{symbol}")
        return data.get("result") if data else None

    async def fetch_public_trades(self, symbol: str) -> Optional[List[Dict]]:
        """Fetches recent public trades for a symbol (Public)."""
        data = await self._request("GET", f"trades/{symbol}")
        return data.get("result") if data else None

    async def fetch_tickers(self) -> List[Ticker]:
        """Fetches tickers for all products."""
        data = await self._request("GET", "tickers")
        if not data or not data.get("result"):
            return []
        
        tickers = []
        for r in data["result"]:
            quotes = r.get("quotes", {})
            tickers.append(Ticker(
                exchange="delta",
                symbol=r["symbol"],
                bid=float(quotes.get("best_bid") or 0),
                ask=float(quotes.get("best_ask") or 0),
                last=float(r.get("close") or 0),
                mark_price=float(r.get("mark_price") or 0) if r.get("mark_price") else None,
                volume_24h=float(r.get("volume") or 0),
                timestamp=int(r.get("timestamp") or 0 / 1000)
            ))
        return tickers

    async def fetch_balances(self) -> List[Balance]:
        """Fetches wallet balances (Authenticated)."""
        data = await self._request("GET", "wallet/balances", auth=True)
        if not data or not data.get("result"):
            return []
        
        return [Balance(
            exchange="delta",
            asset=r["asset_symbol"],
            total=float(r["balance"]),
            available=float(r["available_balance"]),
            blocked=float(r["balance"]) - float(r["available_balance"]),
            timestamp=int(time.time() * 1000)
        ) for r in data["result"]]

    async def fetch_positions(self) -> List[Position]:
        """Fetches margined positions (Authenticated)."""
        data = await self._request("GET", "positions/margined", auth=True)
        if not data or not data.get("result"):
            return []
        
        return [Position(
            exchange="delta",
            symbol=r["symbol"],
            size=float(r["size"]),
            entry_price=float(r["entry_price"]),
            mark_price=float(r["mark_price"]),
            unrealized_pnl=float(r["unrealized_pnl"]),
            margin=float(r["margin"]),
            timestamp=int(time.time() * 1000)
        ) for r in data["result"]]

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Fetches active orders (Authenticated)."""
        params = {"state": "open"}
        if symbol:
            params["product_symbol"] = symbol
        data = await self._request("GET", "orders", params=params, auth=True)
        if not data or not data.get("result"):
            return []
        
        return [self._map_order(r) for r in data["result"]]

    def _map_order(self, r: Dict) -> Order:
        """Maps Delta order response to normalized Order model."""
        # Map side
        side = OrderSide.BUY if r["side"] == "buy" else OrderSide.SELL
        
        # Map type
        type_map = {
            "limit_order": OrderType.LIMIT,
            "market_order": OrderType.MARKET,
            "stop_loss_limit": OrderType.STOP_LOSS_LIMIT,
            "stop_loss_market": OrderType.STOP_LOSS_MARKET,
            "take_profit_limit": OrderType.TAKE_PROFIT_LIMIT,
            "take_profit_market": OrderType.TAKE_PROFIT_MARKET
        }
        o_type = type_map.get(r["order_type"], OrderType.LIMIT)
        
        # Map status
        status_map = {
            "open": OrderStatus.OPEN,
            "closed": OrderStatus.CLOSED,
            "cancelled": OrderStatus.CANCELED,
            "pending": OrderStatus.PENDING,
            "rejected": OrderStatus.REJECTED
        }
        status = status_map.get(r["state"], OrderStatus.OPEN)
        
        # Parse timestamp (V2 uses ISO string, some others might use ms)
        raw_ts = r.get("created_at")
        if isinstance(raw_ts, str):
            try:
                # ISO Format: 2026-02-25T17:59:20.878136Z
                ts = int(datetime.strptime(raw_ts.replace('Z', '+00:00'), "%Y-%m-%dT%H:%M:%S.%f%z").timestamp() * 1000)
            except:
                ts = int(time.time() * 1000)
        else:
            ts = int(raw_ts / 1000) if raw_ts else int(time.time() * 1000)

        return Order(
            id=str(r["id"]),
            exchange="delta",
            symbol=r.get("product_symbol", r.get("symbol", "unknown")),
            side=side,
            type=o_type,
            size=float(r["size"]),
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
            timestamp=ts
        )

    async def place_order(self, symbol: str, size: float, side: str, order_type: str = "limit", 
                          price: Optional[float] = None, stop_price: Optional[float] = None,
                          tp_price: Optional[float] = None, sl_price: Optional[float] = None,
                          tp_limit_price: Optional[float] = None, sl_limit_price: Optional[float] = None) -> Optional[Order]:
        """Places a new order (Authenticated). Supports Bracket orders (SL/TP) and Stop orders."""
        # Map internal type to Delta type
        type_map = {
            "limit": "limit_order",
            "market": "market_order",
            "stop_loss_limit": "stop_loss_limit",
            "stop_loss_market": "stop_loss_market",
            "take_profit_limit": "take_profit_limit",
            "take_profit_market": "take_profit_market"
        }
        delta_type = type_map.get(order_type, "limit_order")
        
        payload = {
            "product_symbol": symbol,
            "size": int(size),
            "side": side,
            "order_type": delta_type
        }
        
        if price:
            payload["limit_price"] = str(price)
        if stop_price:
            payload["stop_price"] = str(stop_price)
            
        # Bracket Orders (V2 Schema: Flat keys for attached SL/TP)
        if sl_price:
            payload["bracket_stop_loss_price"] = str(sl_price)
            if sl_limit_price:
                payload["bracket_stop_loss_limit_price"] = str(sl_limit_price)
                
        if tp_price:
            payload["bracket_take_profit_price"] = str(tp_price)
            if tp_limit_price:
                payload["bracket_take_profit_limit_price"] = str(tp_limit_price)

        if sl_price or tp_price:
            payload["bracket_stop_trigger_method"] = "last_traded_price"

        data = await self._request("POST", "orders", json_data=payload, auth=True)
        if data and data.get("result"):
            return self._map_order(data["result"])
        return None

    async def edit_bracket_order(self, symbol: str, order_id: str, 
                                 sl_price: Optional[float] = None, 
                                 tp_price: Optional[float] = None,
                                 sl_limit: Optional[float] = None,
                                 tp_limit: Optional[float] = None) -> bool:
        """Updates an existing bracket order (Authenticated)."""
        payload = {
            "id": int(order_id),
            "product_symbol": symbol
        }
        if sl_price: payload["bracket_stop_loss_price"] = str(sl_price)
        if sl_limit: payload["bracket_stop_loss_limit_price"] = str(sl_limit)
        if tp_price: payload["bracket_take_profit_price"] = str(tp_price)
        if tp_limit: payload["bracket_take_profit_limit_price"] = str(tp_limit)
        
        data = await self._request("PUT", "orders/bracket", json_data=payload, auth=True)
        return data.get("success", False) if data else False

    async def place_bracket_order(self, symbol: str, 
                                  sl_price: Optional[float] = None, 
                                  tp_price: Optional[float] = None,
                                  sl_limit_price: Optional[float] = None,
                                  tp_limit_price: Optional[float] = None,
                                  trail_amount: Optional[float] = None) -> bool:
        """Places standalone bracket orders for existing positions (Authenticated)."""
        payload = {
            "product_symbol": symbol,
            "bracket_stop_trigger_method": "last_traded_price"
        }
        
        if sl_price or trail_amount:
            payload["stop_loss_order"] = {
                "order_type": "limit_order" if sl_limit_price else "market_order"
            }
            if trail_amount:
                payload["stop_loss_order"]["trail_amount"] = str(trail_amount)
            else:
                payload["stop_loss_order"]["stop_price"] = str(sl_price)
                
            if sl_limit_price:
                payload["stop_loss_order"]["limit_price"] = str(sl_limit_price)
                
        if tp_price:
            payload["take_profit_order"] = {
                "order_type": "limit_order" if tp_limit_price else "market_order",
                "stop_price": str(tp_price)
            }
            if tp_limit_price:
                payload["take_profit_order"]["limit_price"] = str(tp_limit_price)

        data = await self._request("POST", "orders/bracket", json_data=payload, auth=True)
        return data.get("success", False) if data else False

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancels an existing order (Authenticated)."""
        payload = {"product_symbol": symbol, "id": int(order_id)}
        data = await self._request("DELETE", "orders", json_data=payload, auth=True)
        return data.get("success", False) if data else False

    async def fetch_ohlcv(self, symbol: str, timeframe: str, since_ms: int, limit: int = 2000) -> List[Candle]:
        """
        Fetches historical candles from Delta. Handles pagination in chunks of 2000.
        """
        all_candles: List[Candle] = []
        current_since = since_ms
        tf_min = self._timeframe_to_minutes(timeframe)
        
        while len(all_candles) < limit:
            remaining = limit - len(all_candles)
            chunk_limit = min(remaining, 2000)
            
            start_sec = int(current_since / 1000)
            # Delta end is exclusive, so we ask for enough to cover chunk_limit
            end_sec = start_sec + (chunk_limit * tf_min * 60)
            
            params = {
                "resolution": timeframe,
                "symbol": symbol,
                "start": start_sec,
                "end": end_sec
            }
            
            data = await self._request("GET", "history/candles", params=params)
             
            if not data or not data.get("success"):
                break
                
            results = data.get("result", [])
            if not results:
                break
                
            chunk_candles = [
                Candle(
                    symbol=symbol,
                    timestamp_ms=int(r['time'] * 1000),
                    open=float(r['open']),
                    high=float(r['high']),
                    low=float(r['low']),
                    close=float(r['close']),
                    volume=float(r['volume'])
                ) for r in results
            ]
            
            # Sort and append
            chunk_candles.sort(key=lambda x: x.timestamp_ms)
            
            # Filter duplicates (in case overlapping ranges)
            for c in chunk_candles:
                if not all_candles or c.timestamp_ms > all_candles[-1].timestamp_ms:
                    all_candles.append(c)
                if len(all_candles) >= limit:
                    break
            
            # Prepare next start: last candle timestamp + 1 minute (in ms)
            if chunk_candles:
                current_since = all_candles[-1].timestamp_ms + (tf_min * 60 * 1000)
            else:
                break
                
            # Safety break if we aren't making progress
            if len(chunk_candles) == 0:
                break

        return all_candles[:limit]
