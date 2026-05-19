from abc import ABC, abstractmethod
import datetime
from .models import Candle, Ticker, Order, Position, Balance
from typing import List, Optional, Any, Dict

class BaseExchangeAPI(ABC):
    @property
    @abstractmethod
    def rate_limit_ms(self) -> int:
        pass

    def parse8601(self, iso_string: str) -> int:
        dt = datetime.datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return int(dt.timestamp() * 1000)
        
    def iso8601(self, timestamp_ms: int) -> str:
        dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000, datetime.timezone.utc)
        return dt.isoformat()

    def _timeframe_to_minutes(self, timeframe: str) -> int:
        if timeframe.endswith('m'):
            return int(timeframe[:-1])
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 1440
        return 1

    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, timeframe: str, since_ms: int, limit: int = 2000) -> List[Candle]:
        pass

    @abstractmethod
    async def fetch_tickers(self) -> List[Ticker]:
        pass

    @abstractmethod
    async def fetch_balances(self) -> List[Balance]:
        pass

    @abstractmethod
    async def fetch_positions(self) -> List[Position]:
        pass

    @abstractmethod
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        pass

    @abstractmethod
    async def place_order(self, symbol: str, size: float, side: str, order_type: str = "limit", 
                          price: Optional[float] = None, stop_price: Optional[float] = None,
                          tp_price: Optional[float] = None, sl_price: Optional[float] = None,
                          tp_limit_price: Optional[float] = None, sl_limit_price: Optional[float] = None) -> Order:
        pass

    @abstractmethod
    async def place_bracket_order(self, symbol: str, 
                                  sl_price: Optional[float] = None, 
                                  tp_price: Optional[float] = None,
                                  sl_limit_price: Optional[float] = None,
                                  tp_limit_price: Optional[float] = None,
                                  trail_amount: Optional[float] = None) -> bool:
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        pass
