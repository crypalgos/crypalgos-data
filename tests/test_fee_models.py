"""Phase 4 (T-DRY-3): one parametrized MakerTakerFeeModel, exchange models are defaults only."""
from crypalgos_data.common.models import OrderType
from crypalgos_data.exchanges.config.fees import (
    BinanceFeeModel,
    DeltaFeeModel,
    MakerTakerFeeModel,
    OkxFeeModel,
)


def test_maker_taker_split():
    model = MakerTakerFeeModel(maker_fee=0.001, taker_fee=0.002)
    assert model.calculate(OrderType.LIMIT, 2.0, 100.0) == 2.0 * 100.0 * 0.001
    assert model.calculate(OrderType.MARKET, 2.0, 100.0) == 2.0 * 100.0 * 0.002


def test_exchange_models_are_parametrizations():
    for cls, taker in ((DeltaFeeModel, 0.0005), (BinanceFeeModel, 0.0004), (OkxFeeModel, 0.0005)):
        model = cls()
        assert isinstance(model, MakerTakerFeeModel)
        assert model.maker_fee == 0.0002
        assert model.taker_fee == taker


def test_registry_configs_use_shared_model():
    from crypalgos_data.exchanges.config import EXCHANGE_REGISTRY

    for name, cfg_cls in EXCHANGE_REGISTRY.items():
        assert isinstance(cfg_cls().fee_model, MakerTakerFeeModel), name
