import os
import sys
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from crypalgos_data.factory import get_exchange
from crypalgos_data.common.models import OrderSide, OrderType, OrderStatus

def load_local_env():
    """Helper to load env variables from root .env if running tests locally."""
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env'),
        os.path.join(os.getcwd(), '.env')
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val = parts[1].strip().strip('"').strip("'")
                            os.environ[key] = val
                break
            except Exception:
                pass

load_local_env()

API_KEY = os.getenv("DELTA_API_KEY", "")
API_SECRET = os.getenv("DELTA_API_SECRET", "")
SYMBOL = "BTCUSD"

@pytest.fixture
def mock_api():
    """Return a mock API instance with simulated _request."""
    api = get_exchange("delta", api_key="test_key", api_secret="test_secret", testnet=True)
    api._request = AsyncMock()
    return api

@pytest.mark.asyncio
async def test_fetch_tickers_mocked(mock_api):
    # Mock tickers HTTP response
    mock_api._request.return_value = {
        "result": [
            {
                "symbol": "BTCUSD",
                "close": "76500.5",
                "quotes": {"best_bid": "76490.0", "best_ask": "76510.0"},
                "mark_price": "76500.2",
                "volume": "12000.5",
                "timestamp": 1779209580000
            }
        ]
    }

    tickers = await mock_api.fetch_tickers()
    assert len(tickers) == 1
    assert tickers[0].symbol == "BTCUSD"
    assert tickers[0].last == 76500.5
    assert tickers[0].bid == 76490.0
    assert tickers[0].ask == 76510.0
    assert tickers[0].volume_24h == 12000.5

@pytest.mark.asyncio
async def test_fetch_balances_mocked(mock_api):
    # Mock balances response
    mock_api._request.return_value = {
        "result": [
            {
                "asset_symbol": "USDT",
                "balance": "10000.5",
                "available_balance": "9500.0"
            }
        ]
    }

    balances = await mock_api.fetch_balances()
    assert len(balances) == 1
    assert balances[0].asset == "USDT"
    assert balances[0].total == 10000.5
    assert balances[0].available == 9500.0
    assert balances[0].blocked == 500.5

@pytest.mark.asyncio
async def test_place_order_mocked(mock_api):
    # Mock order placement response
    mock_api._request.return_value = {
        "result": {
            "id": 12345,
            "product_symbol": "BTCUSD",
            "side": "buy",
            "order_type": "limit_order",
            "size": 5,
            "limit_price": "70000.0",
            "state": "open",
            "filled_size": "0",
            "updated_at": "2026-05-19T22:24:00Z"
        }
    }

    order = await mock_api.place_order(
        symbol="BTCUSD",
        size=5,
        side="buy",
        order_type="limit",
        price=70000.0
    )
    assert order is not None
    assert order.id == "12345"
    assert order.side == OrderSide.BUY
    assert order.type == OrderType.LIMIT
    assert order.price == 70000.0
    assert order.status == OrderStatus.OPEN

@pytest.mark.asyncio
async def test_cancel_order_mocked(mock_api):
    mock_api._request.return_value = {"success": True}

    success = await mock_api.cancel_order("BTCUSD", "12345")
    assert success is True

# Live test condition
has_keys = bool(API_KEY and API_SECRET)

@pytest.mark.asyncio
@pytest.mark.skipif(not has_keys, reason="DELTA_API_KEY and DELTA_API_SECRET not set in environment.")
async def test_live_rest_testnet():
    """Verify live connectivity if keys are provided, failing/skipping gracefully if IP whitelisting blocks."""
    api = get_exchange("delta", api_key=API_KEY, api_secret=API_SECRET, testnet=True)
    
    try:
        # Public connectivity check
        tickers = await api.fetch_tickers()
        assert len(tickers) > 0
        
        # Private authentication check (balances)
        balances = await api.fetch_balances()
        if balances is not None:
            assert isinstance(balances, list)
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401 and "ip_not_whitelisted" in e.response.text:
            pytest.skip(f"Live keys present but blocked by Delta IP Whitelisting: {e.response.json()}")
        else:
            raise e
