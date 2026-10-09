from typing import Dict, Type
from .common.base_api import BaseExchangeAPI
from .common.base_stream import BaseExchangeClient
from .exchanges.delta import DeltaAPI
from .stream.exchanges.delta import DeltaExchangeClient

class ExchangeFactory:
    _exchanges: Dict[str, Type[BaseExchangeAPI]] = {
        "delta": DeltaAPI
    }

    _stream_clients: Dict[str, Type[BaseExchangeClient]] = {
        "delta": DeltaExchangeClient
    }

    @classmethod
    def get_exchange(cls, name: str, **kwargs) -> BaseExchangeAPI:
        """
        Returns an instance of the REST exchange API by name.
        """
        name = name.lower()
        if name not in cls._exchanges:
            raise ValueError(f"Exchange '{name}' is not supported.")
        
        return cls._exchanges[name](**kwargs)

    @classmethod
    def get_stream_client(cls, name: str, broker, **kwargs) -> BaseExchangeClient:
        """
        Returns an instance of the WebSocket exchange client by name.
        """
        name = name.lower()
        if name not in cls._stream_clients:
            raise ValueError(f"Exchange stream client '{name}' is not supported.")
        
        return cls._stream_clients[name](broker, **kwargs)

def get_exchange(name: str, **kwargs) -> BaseExchangeAPI:
    """Convenience function to get a REST exchange instance."""
    return ExchangeFactory.get_exchange(name, **kwargs)

def get_stream_client(name: str, broker, **kwargs) -> BaseExchangeClient:
    """Convenience function to get a WebSocket stream client instance."""
    return ExchangeFactory.get_stream_client(name, broker, **kwargs)
