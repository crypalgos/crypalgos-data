import os
import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from crypalgos_data.factory import get_exchange
from crypalgos_data.common.models import OrderSide, OrderType, OrderStatus

@pytest.fixture
def mock_api():
    """Return a mock API instance with simulated _request."""
    api = get_exchange("delta", api_key="test_key", api_secret="test_secret", testnet=True)
    api._request = AsyncMock()
    return api

@pytest.mark.asyncio
async def test_place_bracket_order_standalone_mocked(mock_api):
    # Standalone stop-loss/take-profit bracket orders
    mock_api._request.return_value = {"success": True}

    success = await mock_api.place_bracket_order(
        symbol="BTCUSD",
        sl_price=74000.0,
        tp_price=78000.0
    )
    assert success is True
    
    # Assert _request called with correct arguments
    mock_api._request.assert_called_once()
    args, kwargs = mock_api._request.call_args
    assert args[0] == "POST"
    assert args[1] == "orders/bracket"
    payload = kwargs["json_data"]
    assert payload["product_symbol"] == "BTCUSD"
    assert payload["stop_loss_order"]["stop_price"] == "74000.0"
    assert payload["take_profit_order"]["stop_price"] == "78000.0"

@pytest.mark.asyncio
async def test_place_order_with_attached_brackets_mocked(mock_api):
    # Order entry + attached SL/TP brackets (flat schema)
    mock_api._request.return_value = {
        "result": {
            "id": 55555,
            "product_symbol": "BTCUSD",
            "side": "buy",
            "order_type": "limit_order",
            "size": 1,
            "limit_price": "75000.0",
            "state": "open",
            "filled_size": "0",
            "bracket_stop_loss_price": "70000.0",
            "bracket_take_profit_price": "80000.0",
            "updated_at": "2026-05-19T22:24:00Z"
        }
    }

    order = await mock_api.place_order(
        symbol="BTCUSD",
        size=1,
        side="buy",
        order_type="limit",
        price=75000.0,
        sl_price=70000.0,
        tp_price=80000.0
    )
    
    assert order is not None
    assert order.id == "55555"
    assert order.sl_price == 70000.0
    assert order.tp_price == 80000.0
    
    mock_api._request.assert_called_once()
    args, kwargs = mock_api._request.call_args
    payload = kwargs["json_data"]
    assert payload["bracket_stop_loss_price"] == "70000.0"
    assert payload["bracket_take_profit_price"] == "80000.0"

@pytest.mark.asyncio
async def test_edit_bracket_order_mocked(mock_api):
    # Edit SL/TP bounds on an existing entry order (PUT /orders/bracket)
    mock_api._request.return_value = {"success": True}

    success = await mock_api.edit_bracket_order(
        symbol="BTCUSD",
        order_id="55555",
        sl_price=71000.0,
        tp_price=79000.0
    )
    assert success is True
    
    # Verify HTTP PUT is called
    mock_api._request.assert_called_once()
    args, kwargs = mock_api._request.call_args
    assert args[0] == "PUT"
    assert args[1] == "orders/bracket"
    payload = kwargs["json_data"]
    assert payload["id"] == 55555
    assert payload["product_symbol"] == "BTCUSD"
    assert payload["bracket_stop_loss_price"] == "71000.0"
    assert payload["bracket_take_profit_price"] == "79000.0"

@pytest.mark.asyncio
async def test_place_bracket_order_trailing_sl_mocked(mock_api):
    # Trailing Stop-loss standalone order
    mock_api._request.return_value = {"success": True}

    success = await mock_api.place_bracket_order(
        symbol="BTCUSD",
        sl_price=None,
        trail_amount=150.0
    )
    assert success is True
    
    # Assert trailing SL structure
    args, kwargs = mock_api._request.call_args
    payload = kwargs["json_data"]
    assert payload["stop_loss_order"]["trail_amount"] == "150.0"
    assert "take_profit_order" not in payload
