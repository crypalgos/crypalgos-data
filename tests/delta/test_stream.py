import os
import sys
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from crypalgos_data.factory import get_stream_client
from crypalgos_data.stream.manager import StreamerManager
from crypalgos_data.stream.subscriber import StreamSubscriber
from crypalgos_data.common.models import OrderSide, OrderType, OrderStatus

@pytest.fixture
def mock_broker():
    """Return a mock broker with publish tracking."""
    broker = MagicMock()
    broker.publish = AsyncMock()
    return broker

@pytest.fixture
def mock_client(mock_broker):
    """Return a Delta WebSocket client with mock setup."""
    return get_stream_client(
        "delta",
        broker=mock_broker,
        symbols=["BTCUSD"],
        api_key="test_key",
        api_secret="test_secret",
        testnet=True
    )

def test_stream_client_init(mock_client):
    assert mock_client.exchange_name == "delta"
    assert mock_client.symbols == ["BTCUSD"]
    assert "socket-ind.testnet.deltaex.org" in mock_client.ws_url

def test_get_subscription_payload(mock_client):
    payload = mock_client.get_subscription_payload()
    assert payload["type"] == "subscribe"
    channels = payload["payload"]["channels"]
    
    # Check if orders, positions, and balances are included since api_key is present
    channel_names = [c["name"] for c in channels]
    assert "all_trades" in channel_names
    assert "candlestick_1m" in channel_names
    assert "v2/ticker" in channel_names
    assert "orders" in channel_names
    assert "positions" in channel_names

def test_normalize_message_trade(mock_client):
    raw_trade = {
        "type": "all_trades",
        "symbol": "BTCUSD",
        "price": "76000.5",
        "size": "2.5",
        "timestamp": 1779209580000,
        "buyer_role": "maker"
    }
    
    normalized = mock_client.normalize_message(raw_trade)
    assert normalized is not None
    topic, data = normalized
    assert topic == "trade"
    assert data.exchange == "delta"
    assert data.symbol == "BTCUSD"
    assert data.price == 76000.5
    assert data.amount == 2.5
    assert data.side == OrderSide.SELL

def test_normalize_message_candlestick(mock_client):
    raw_candle = {
        "type": "candlestick_1m",
        "timestamp": 1779209580000,
        "open": "76000.0",
        "high": "76100.0",
        "low": "75900.0",
        "close": "76050.0",
        "volume": "15.0"
    }
    
    normalized = mock_client.normalize_message(raw_candle)
    assert normalized is not None
    topic, data = normalized
    assert topic == "ohlcv"
    assert data.timestamp_ms == 1779209580000
    assert data.open == 76000.0
    assert data.close == 76050.0
    assert data.volume == 15.0

def test_normalize_message_ticker(mock_client):
    raw_ticker = {
        "type": "v2/ticker",
        "symbol": "BTCUSD",
        "close": "76050.0",
        "mark_price": "76045.0",
        "volume": "50000.0",
        "timestamp": 1779209580000,
        "quotes": {
            "best_bid": "76040.0",
            "best_ask": "76060.0"
        },
        "oi": 1200.5,
        "oi_value": 91200000.0,
        "greeks": {
            "delta": "0.45",
            "gamma": "0.0002",
            "theta": "-15.5",
            "vega": "120.0",
            "rho": "5.0",
            "iv": "0.65"
        }
    }
    
    updates = mock_client.normalize_message(raw_ticker)
    assert isinstance(updates, list)
    
    # Verify ticker
    ticker_update = [u for u in updates if u[0] == "ticker"][0]
    assert ticker_update is not None
    ticker_data = ticker_update[1]
    assert ticker_data.symbol == "BTCUSD"
    assert ticker_data.bid == 76040.0
    assert ticker_data.ask == 76060.0
    assert ticker_data.last == 76050.0

    # Verify Greeks
    greeks_update = [u for u in updates if u[0] == "option_greeks"][0]
    assert greeks_update is not None
    greeks_data = greeks_update[1]
    assert greeks_data.delta == 0.45
    assert greeks_data.iv == 0.65

    # Verify Mark Price
    mp_update = [u for u in updates if u[0] == "mark_price"][0]
    assert mp_update is not None
    assert mp_update[1].mark_price == 76045.0

    # Verify Open Interest
    oi_update = [u for u in updates if u[0] == "open_interest"][0]
    assert oi_update is not None
    assert oi_update[1].open_interest == 1200.5

@pytest.mark.asyncio
async def test_streamer_manager_creation():
    manager = StreamerManager(
        exchange_name="delta",
        broker_address="tcp://127.0.0.1:9999",
        symbols=["BTCUSD"],
        api_key="key",
        api_secret="secret",
        testnet=True
    )
    assert len(manager.clients) == 1
    assert manager.clients[0].exchange_name == "delta"


def test_normalize_message_current_delta_ticker_uses_last_price_and_ms_timestamp(mock_client):
    updates = mock_client.normalize_message(
        {
            "type": "v2/ticker",
            "symbol": "BTCUSD",
            "last_price": "76100.5",
            "mark_price": "75900.0",
            "best_bid": "76100.0",
            "best_ask": "76101.0",
            "timestamp": 1_700_000_000_123_456,
        }
    )

    ticker = next(data for topic, data in updates if topic == "ticker")
    assert ticker.last == 76100.5
    assert ticker.mark_price == 75900.0
    assert ticker.timestamp == 1_700_000_000_123
