import zmq
import zmq.asyncio
import logging
import os
import json
from typing import Optional, Any, Union

logger = logging.getLogger(__name__)

class ZMQBroker:
    """
    A ZMQ Broker that handles publishing market data.
    In a microservices setup, this service 'binds' to an address (TCP or IPC).
    """
    def __init__(self, address: Optional[str] = None):
        self.address = address or os.getenv("CRYPALGOS_ZMQ_ADDRESS", "ipc:///tmp/data_streamer.ipc")
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.is_running = False

    async def start(self):
        try:
            # For a streamer service (Producer), we bind to the address
            self.socket.bind(self.address)
            self.is_running = True
            logger.info(f"ZMQ Broker (Producer) bound to {self.address}")
        except Exception as e:
            logger.error(f"Failed to bind ZMQ Broker: {e}")
            raise

    async def publish(self, topic: str, data: Union[str, Any]):
        if not self.is_running:
            return
        
        try:
            # Auto-serialize Pydantic models or dicts
            if hasattr(data, "model_dump_json"):
                data_str = data.model_dump_json()
            elif isinstance(data, (dict, list)):
                data_str = json.dumps(data)
            else:
                data_str = str(data)

            await self.socket.send_multipart([
                topic.encode("utf-8"),
                data_str.encode("utf-8")
            ])
        except Exception as e:
            logger.error(f"Error publishing to ZMQ: {e}")

    async def stop(self):
        self.is_running = False
        self.socket.close()
        self.context.term()
        logger.info("ZMQ Broker stopped")
