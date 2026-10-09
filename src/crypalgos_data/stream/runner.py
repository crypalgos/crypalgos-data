import asyncio
import logging
import os
import signal
import sys
from ..stream.manager import StreamerManager

logger = logging.getLogger("StreamerService")

def load_local_env():
    """Pure-Python .env file loader to dynamically load keys without dependencies."""
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
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

def main():
    """CLI entry point for the production streamer service."""
    # Configure Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load environment variables
    load_local_env()
    
    # 1. Determine target exchange (CLI arg or environment variable or default)
    exchange_name = sys.argv[1] if len(sys.argv) > 1 else os.getenv("EXCHANGE_NAME", "delta").lower()
    
    # 2. Load API credentials dynamically based on exchange name
    env_prefix = exchange_name.upper()
    api_key = os.getenv(f"{env_prefix}_API_KEY", "")
    api_secret = os.getenv(f"{env_prefix}_API_SECRET", "")
    
    # 3. Load configurations
    broker_address = os.getenv("CRYPALGOS_ZMQ_ADDRESS", "tcp://0.0.0.0:5555")
    symbols_env = os.getenv("CRYPALGOS_SYMBOLS", "BTCUSD,ETHUSD,SOLUSD,XRPUSD")
    symbols = [s.strip() for s in symbols_env.split(",") if s.strip()]

    logger.info(f"Starting Production Streamer Service for exchange: {exchange_name.upper()}")
    logger.info(f"ZMQ Broker Address: {broker_address}")
    logger.info(f"Monitoring symbols: {symbols}")

    manager = StreamerManager(
        exchange_name=exchange_name,
        broker_address=broker_address,
        symbols=symbols,
        api_key=api_key if api_key else None,
        api_secret=api_secret if api_secret else None,
        testnet=True # Running in testnet mode for development/testing
    )
    
    async def run_service():
        # Handle shutdown signals
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def stop_handler():
            logger.info("Shutdown signal received...")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_handler)
            except NotImplementedError:
                # Signal handlers are not fully supported on some platforms/Windows loops
                pass

        try:
            await manager.start()
            logger.info("Streamer Service is running. Press Ctrl+C to stop.")
            
            # Keep the service running until stop signal
            await stop_event.wait()
            
        except Exception as e:
            logger.error(f"Streamer Service fatal error: {e}")
        finally:
            await manager.stop()
            logger.info("Streamer Service shutdown complete.")

    try:
        asyncio.run(run_service())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
