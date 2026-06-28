from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any
from datetime import timedelta
from ...common.models import OrderSide, OrderType

class FeeModel(ABC):
    @abstractmethod
    def calculate(self, order_type: OrderType, quantity: float, price: float, account: Optional[Any] = None) -> float:
        pass

class FundingModel(ABC):
    interval: timedelta

    def __init__(self, interval: timedelta):
        self.interval = interval

    @abstractmethod
    def calculate_payment(self, position_size: float, mark_price: float, funding_rate: float) -> float:
        pass

class LiquidationModel(ABC):
    @abstractmethod
    def calculate_liquidation_price(self, side: str, size: float, entry_price: float, margin: float) -> float:
        pass

@dataclass(frozen=True)
class PrecisionRules:
    price_decimals: int
    quantity_decimals: int

@dataclass(frozen=True)
class LeverageRules:
    max_leverage: int

@dataclass(frozen=True)
class ExchangeConfig:
    id: str
    name: str

    fee_model: FeeModel
    funding_model: FundingModel
    liquidation_model: LiquidationModel

    precision: PrecisionRules
    leverage_rules: LeverageRules
