from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP_LOSS_LIMIT = "stop_loss_limit"
    STOP_LOSS_MARKET = "stop_loss_market"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    TAKE_PROFIT_MARKET = "take_profit_market"

class OrderStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELED = "canceled"
    PENDING = "pending"
    REJECTED = "rejected"

class Candle(BaseModel):
    symbol: Optional[str] = None
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_list(self) -> List:
        return [self.timestamp_ms, self.open, self.high, self.low, self.close, self.volume]

class Ticker(BaseModel):
    exchange: str
    symbol: str
    bid: float
    ask: float
    last: float
    mark_price: Optional[float] = None
    volume_24h: float
    timestamp: int

class Order(BaseModel):
    id: str
    exchange: str
    symbol: str
    side: OrderSide
    type: OrderType
    size: float
    price: Optional[float] = None
    status: OrderStatus
    filled_size: float = 0.0
    average_price: Optional[float] = None
    stop_price: Optional[float] = None
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None
    timestamp: int

class Position(BaseModel):
    exchange: str
    symbol: str
    size: float  # Positive for long, negative for short
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    margin: float
    timestamp: int

class Balance(BaseModel):
    exchange: str
    asset: str
    total: float
    available: float
    blocked: float
    timestamp: int

class Trade(BaseModel):
    exchange: str
    symbol: str
    price: float
    amount: float
    side: OrderSide
    timestamp: int
