import zmq
import zmq.asyncio
import json
import logging
import os
from typing import Optional, List, Callable, Awaitable

logger = logging.getLogger(__name__)

class StreamSubscriber:
    """
    A ZMQ Subscriber that simplifies receiving market data from the Streamer Service.
    In a microservices setup, this client 'connects' to the streamer service address.
    """
    def __init__(self, address: Optional[str] = None):
        self.address = address or os.getenv("CRYPALGOS_ZMQ_ADDRESS", "ipc:///tmp/data_streamer.ipc")
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.is_running = False

    async def connect(self, topics: List[str] = ["ohlcv.delta"]):
        """
        Connects to the ZMQ broker and subscribes to the given topics.
        """
        try:
            self.socket.connect(self.address)
            for topic in topics:
                self.socket.setsockopt(zmq.SUBSCRIBE, topic.encode('utf-8'))
            
            self.is_running = True
            logger.info(f"StreamSubscriber connected to {self.address}, subscribed to {topics}")
        except Exception as e:
            logger.error(f"Failed to connect StreamSubscriber: {e}")
            raise

    async def listen(self, callback: Callable[[str, dict], Awaitable[None]]):
        """
        Listens for incoming messages and executes the callback for each.
        """
        try:
            while self.is_running:
                multipart = await self.socket.recv_multipart()
                if len(multipart) == 2:
                    topic, data = multipart
                    msg_topic = topic.decode('utf-8')
                    msg_data = json.loads(data.decode('utf-8'))
                    await callback(msg_topic, msg_data)
        except zmq.ZMQError as e:
            if self.is_running:
                logger.error(f"ZMQ Subscriber listening error: {e}")
        except Exception as e:
            logger.error(f"Subscriber error: {e}")

    async def stop(self):
        self.is_running = False
        self.socket.close()
        self.context.term()
        logger.info("StreamSubscriber stopped")
