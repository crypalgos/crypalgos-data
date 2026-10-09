from .models import LiquidationModel

class DefaultLiquidationModel(LiquidationModel):
    def __init__(self, maintenance_margin_ratio: float = 0.005):
        self.mmr = maintenance_margin_ratio

    def calculate_liquidation_price(self, side: str, size: float, entry_price: float, margin: float) -> float:
        abs_size = abs(size)
        if abs_size == 0:
            return 0.0

        if side.upper() == "LONG":
            denom = abs_size * (1.0 - self.mmr)
            if denom == 0.0:
                return 0.0
            return (abs_size * entry_price - margin) / denom
        else:
            denom = abs_size * (1.0 + self.mmr)
            if denom == 0.0:
                return 0.0
            return (margin + abs_size * entry_price) / denom
