import asyncio
import logging
from typing import List, Optional
from .broker import ZMQBroker
from ..factory import get_stream_client

logger = logging.getLogger(__name__)

class StreamerManager:
    def __init__(self, exchange_name: str = "delta", broker_address: Optional[str] = None, 
                 symbols: List[str] = ["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD"], 
                 api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False):
        self.broker = ZMQBroker(address=broker_address)
        
        # Instantiate stream client dynamically using the factory
        client = get_stream_client(
            exchange_name,
            self.broker,
            symbols=symbols,
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet
        )
        self.clients = [client]
        self.tasks = []

    async def start(self):
        logger.info("Starting Data Streamer...")
        await self.broker.start()
        
        for client in self.clients:
            task = asyncio.create_task(client.connect())
            self.tasks.append(task)
        
        logger.info("All exchange clients started")

    async def stop(self):
        logger.info("Stopping Data Streamer...")
        for client in self.clients:
            await client.stop()
        
        for task in self.tasks:
            task.cancel()
        
        await self.broker.stop()
        logger.info("Data Streamer stopped")
