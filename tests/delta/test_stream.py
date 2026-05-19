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
        }
    }
    
    normalized = mock_client.normalize_message(raw_ticker)
    assert normalized is not None
    topic, data = normalized
    assert topic == "ticker"
    assert data.symbol == "BTCUSD"
    assert data.bid == 76040.0
    assert data.ask == 76060.0
    assert data.last == 76050.0

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
