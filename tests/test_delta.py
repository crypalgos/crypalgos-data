import pytest
from unittest.mock import AsyncMock
from crypalgos_data.exchanges.delta import DeltaAPI

@pytest.fixture
def delta_api():
    api = DeltaAPI()
    api._request = AsyncMock()
    return api

@pytest.mark.asyncio
async def test_delta_fetch_ohlcv_success(delta_api):
    symbol = "BTCUSD"
    timeframe = "1m"
    since_ms = 1704067200000
    
    mock_response = {
        "success": True,
        "result": [
            {
                "time": 1704067200,
                "open": "42000.0",
                "high": "42100.0",
                "low": "41900.0",
                "close": "42050.0",
                "volume": "10.5"
            }
        ]
    }
    
    delta_api._request.return_value = mock_response
    
    candles = await delta_api.fetch_ohlcv(symbol, timeframe, since_ms, limit=1)
    
    assert len(candles) == 1
    assert candles[0].timestamp_ms == 1704067200000
    assert candles[0].open == 42000.0
    assert candles[0].close == 42050.0
    assert candles[0].volume == 10.5
    
    delta_api._request.assert_called_once()
    args, kwargs = delta_api._request.call_args
    assert args[0] == "GET"
    assert args[1] == "history/candles"

@pytest.mark.asyncio
async def test_delta_fetch_ohlcv_failure(delta_api):
    symbol = "BTCUSD"
    timeframe = "1m"
    since_ms = 1704067200000
    
    delta_api._request.return_value = {
        "success": False,
        "error": "Invalid symbol"
    }
    
    candles = await delta_api.fetch_ohlcv(symbol, timeframe, since_ms, limit=1)
    assert candles == []
