from typing import Optional, Any
from ...common.models import OrderType
from .models import FeeModel

class DeltaFeeModel(FeeModel):
    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

    def calculate(self, order_type: OrderType, quantity: float, price: float, account: Optional[Any] = None) -> float:
        rate = self.maker_fee if order_type == OrderType.LIMIT else self.taker_fee
        return quantity * price * rate

class BinanceFeeModel(FeeModel):
    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0004):
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

    def calculate(self, order_type: OrderType, quantity: float, price: float, account: Optional[Any] = None) -> float:
        rate = self.maker_fee if order_type == OrderType.LIMIT else self.taker_fee
        return quantity * price * rate

class OkxFeeModel(FeeModel):
    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

    def calculate(self, order_type: OrderType, quantity: float, price: float, account: Optional[Any] = None) -> float:
        rate = self.maker_fee if order_type == OrderType.LIMIT else self.taker_fee
        return quantity * price * rate
