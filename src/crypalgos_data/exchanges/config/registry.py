from datetime import timedelta
from typing import Dict, Type
from .models import ExchangeConfig, PrecisionRules, LeverageRules
from .fees import DeltaFeeModel, BinanceFeeModel, OkxFeeModel
from .funding import DefaultFundingModel
from .liquidation import DefaultLiquidationModel

class DeltaConfig(ExchangeConfig):
    def __init__(self):
        super().__init__(
            id="delta",
            name="Delta Exchange",
            fee_model=DeltaFeeModel(),
            funding_model=DefaultFundingModel(interval=timedelta(hours=8)),
            liquidation_model=DefaultLiquidationModel(maintenance_margin_ratio=0.005),
            precision=PrecisionRules(price_decimals=4, quantity_decimals=4),
            leverage_rules=LeverageRules(max_leverage=100)
        )

class BinanceConfig(ExchangeConfig):
    def __init__(self):
        super().__init__(
            id="binance",
            name="Binance",
            fee_model=BinanceFeeModel(),
            funding_model=DefaultFundingModel(interval=timedelta(hours=8)),
            liquidation_model=DefaultLiquidationModel(maintenance_margin_ratio=0.004),
            precision=PrecisionRules(price_decimals=4, quantity_decimals=4),
            leverage_rules=LeverageRules(max_leverage=125)
        )

class OkxConfig(ExchangeConfig):
    def __init__(self):
        super().__init__(
            id="okx",
            name="OKX",
            fee_model=OkxFeeModel(),
            funding_model=DefaultFundingModel(interval=timedelta(hours=8)),
            liquidation_model=DefaultLiquidationModel(maintenance_margin_ratio=0.005),
            precision=PrecisionRules(price_decimals=4, quantity_decimals=4),
            leverage_rules=LeverageRules(max_leverage=100)
        )

EXCHANGE_REGISTRY: Dict[str, Type[ExchangeConfig]] = {
    "delta": DeltaConfig,
    "binance": BinanceConfig,
    "okx": OkxConfig
}
