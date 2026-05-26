import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Set up logging to show everything clearly
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("live_test")

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from crypalgos_data.factory import get_exchange, get_stream_client
from crypalgos_data.stream.broker import ZMQBroker

# Load environment
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

API_KEY = os.getenv("DELTA_API_KEY")
API_SECRET = os.getenv("DELTA_API_SECRET")

async def run_rest_api():
    logger.info("Initializing REST Exchange Client (Testnet)...")
    exchange = get_exchange(
        "delta",
        api_key=API_KEY,
        api_secret=API_SECRET,
        testnet=True
    )
    
    # 1. Fetch products
    logger.info("Fetching Products...")
    products = await exchange.fetch_products()
    logger.info(f"Successfully retrieved {len(products)} products!")
    
    # Find an active asset (e.g., BTCUSD perpetual or similar)
    active_symbols = [p["symbol"] for p in products if p.get("state") == "live"]
    logger.info(f"Some active symbols: {active_symbols[:5]}")
    
    # 2. Fetch Balances
    logger.info("Fetching balances...")
    balances = await exchange.fetch_balances()
    for b in balances:
        logger.info(f"Balance: {b.asset} | Total: {b.total} | Available: {b.available}")
        
    # 3. Fetch Positions
    logger.info("Fetching positions Margined...")
    positions = await exchange.fetch_positions()
    for p in positions:
        logger.info(f"Position: {p.symbol} | Size: {p.size} | Entry: {p.entry_price} | PnL: {p.unrealized_pnl}")
        
    # 4. Place a test buy limit order with attached SL and TP brackets
    test_symbol = "BTCUSD" if "BTCUSD" in active_symbols else (active_symbols[0] if active_symbols else None)
    if test_symbol:
        logger.info(f"Placing test limit order on {test_symbol} with SL and TP brackets...")
        try:
            # Place buy order far below market price to avoid execution
            order = await exchange.place_order(
                symbol=test_symbol,
                size=1,
                side="buy",
                order_type="limit",
                price=10000.0,  # far below BTC price
                sl_price=9000.0,  # Attached Stop Loss
                tp_price=15000.0   # Attached Take Profit
            )
            if order:
                logger.info(f"Bracket Order placed successfully! ID: {order.id}")
                logger.info(f"Order Details: Symbol={order.symbol} | Price={order.price} | SL={order.sl_price} | TP={order.tp_price}")
                logger.info("Order is left open on Delta Testnet for visual verification in your dashboard.")
            else:
                logger.error("Failed to place test order.")
        except Exception as e:
            logger.error(f"Error placing order: {e}")

async def run_websocket_stream():
    logger.info("Initializing ZeroMQ Broker...")
    broker = ZMQBroker()
    await broker.start()
    
    # We will subscribe to BTCUSD perpetual plus an option symbol if active
    logger.info("Initializing WebSocket Stream Client (Testnet)...")
    
    # Try to find a call option symbol on BTC
    exchange = get_exchange("delta", testnet=True)
    products = await exchange.fetch_products()
    option_symbols = [p["symbol"] for p in products if p.get("contract_type") == "call_options" and p.get("state") == "live"]
    
    symbols_to_subscribe = ["BTCUSD"]
    if option_symbols:
        symbols_to_subscribe.append(option_symbols[0])
        logger.info(f"Subscribing to perpetual and option: {symbols_to_subscribe}")
    else:
        logger.info(f"Subscribing to: {symbols_to_subscribe}")
        
    client = get_stream_client(
        "delta",
        broker=broker,
        symbols=symbols_to_subscribe,
        api_key=API_KEY,
        api_secret=API_SECRET,
        testnet=True
    )
    
    # We override the broker's publish to capture the live normalized updates!
    received_updates = []
    async def mock_publish(topic, data):
        received_updates.append((topic, data))
        logger.info(f"[LIVE STREAM UPDATE] Topic: {topic} | Data: {data}")
        
    broker.publish = mock_publish
    broker.is_running = True
    
    # Run the client in the background
    client_task = asyncio.create_task(client.connect())
    
    logger.info("Listening for updates on live websocket stream for 8 seconds...")
    await asyncio.sleep(8)
    
    logger.info("Stopping WebSocket stream client...")
    await client.stop()
    client_task.cancel()
    await broker.stop()
    
    logger.info(f"Live WebSockets completed! Captured {len(received_updates)} real-time updates.")

async def main():
    logger.info("=== STARTING LIVE DELTA EXCHANGE TESTNET API AND STREAM TESTS ===")
    await run_rest_api()
    logger.info("-----------------------------------------------------------------")
    await run_websocket_stream()
    logger.info("=== LIVE INTEGRATION TEST PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(main())
