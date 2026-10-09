from datetime import timedelta
from .models import FundingModel

class DefaultFundingModel(FundingModel):
    def __init__(self, interval: timedelta = timedelta(hours=8)):
        super().__init__(interval=interval)

    def calculate_payment(self, position_size: float, mark_price: float, funding_rate: float) -> float:
        # Standard perpetual funding calculation
        return position_size * mark_price * funding_rate
