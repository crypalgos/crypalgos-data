from typing import Optional, Any
from ...common.models import OrderType
from .models import FeeModel


class MakerTakerFeeModel(FeeModel):
    """Standard maker/taker fee model: LIMIT orders pay maker, everything else taker.

    All exchange fee models are instances of this with different default rates —
    never copy-paste a new class for a new exchange, just parametrize.
    """

    def __init__(self, maker_fee: float, taker_fee: float):
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

    def calculate(self, order_type: OrderType, quantity: float, price: float, account: Optional[Any] = None) -> float:
        rate = self.maker_fee if order_type == OrderType.LIMIT else self.taker_fee
        return quantity * price * rate


class DeltaFeeModel(MakerTakerFeeModel):
    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        super().__init__(maker_fee, taker_fee)


class BinanceFeeModel(MakerTakerFeeModel):
    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0004):
        super().__init__(maker_fee, taker_fee)


class OkxFeeModel(MakerTakerFeeModel):
    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        super().__init__(maker_fee, taker_fee)
