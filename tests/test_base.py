import pytest
from crypalgos_data.common.base_api import BaseExchangeAPI
from crypalgos_data.common.models import Candle, Ticker, Balance, Position, Order
from typing import List, Optional

class MockExchangeAPI(BaseExchangeAPI):
    @property
    def rate_limit_ms(self) -> int:
        return 100

    async def fetch_ohlcv(self, symbol: str, timeframe: str, since_ms: int, limit: int = 2000) -> List[Candle]:
        return []

    async def fetch_tickers(self) -> List[Ticker]:
        return []

    async def fetch_balances(self) -> List[Balance]:
        return []

    async def fetch_positions(self) -> List[Position]:
        return []

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        return []

    async def place_order(self, symbol: str, size: float, side: str, order_type: str = "limit", 
                          price: Optional[float] = None, stop_price: Optional[float] = None,
                          tp_price: Optional[float] = None, sl_price: Optional[float] = None,
                          tp_limit_price: Optional[float] = None, sl_limit_price: Optional[float] = None) -> Order:
        return None

    async def place_bracket_order(self, symbol: str, 
                                  sl_price: Optional[float] = None, 
                                  tp_price: Optional[float] = None,
                                  sl_limit_price: Optional[float] = None,
                                  tp_limit_price: Optional[float] = None,
                                  trail_amount: Optional[float] = None) -> bool:
        return False

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        return False

@pytest.fixture
def api():
    return MockExchangeAPI()

def test_parse8601(api):
    iso_str = "2024-01-01T00:00:00Z"
    ts = api.parse8601(iso_str)
    assert ts == 1704067200000

def test_iso8601(api):
    ts = 1704067200000
    iso_str = api.iso8601(ts)
    assert "2024-01-01T00:00:00" in iso_str

def test_timeframe_to_minutes(api):
    assert api._timeframe_to_minutes("1m") == 1
    assert api._timeframe_to_minutes("5m") == 5
    assert api._timeframe_to_minutes("1h") == 60
    assert api._timeframe_to_minutes("1d") == 1440
    assert api._timeframe_to_minutes("unknown") == 1

def test_candle_to_list():
    candle = Candle(
        timestamp_ms=1000,
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=10.0
    )
    assert candle.to_list() == [1000, 1.0, 2.0, 0.5, 1.5, 10.0]
