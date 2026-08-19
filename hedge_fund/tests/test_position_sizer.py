import pytest

from hedge_fund.risk.position_sizer import PositionSizer, PositionSizerConfig


class TestPositionSizer:
    def setup_method(self):
        self.sizer = PositionSizer()

    def test_normal_calculation(self):
        result = self.sizer.calculate("SBER", 1_000_000, 0.8, 5.0, 250.0)
        assert result.recommended_qty >= 1
        assert result.position_value > 0
        assert result.portfolio_fraction > 0

    def test_minimum_qty_is_one(self):
        result = self.sizer.calculate("SBER", 1_000_000, 0.01, 100.0, 250.0)
        assert result.recommended_qty >= 1

    def test_max_position_cap(self):
        config = PositionSizerConfig(max_position_pct=5.0)
        sizer = PositionSizer(config)
        result = sizer.calculate("SBER", 1_000_000, 1.0, 0.01, 100.0)
        max_value = 1_000_000 * 5.0 / 100.0
        assert result.position_value <= max_value + 100  # allow 1 lot rounding

    def test_zero_price_returns_zero(self):
        result = self.sizer.calculate("SBER", 1_000_000, 0.8, 5.0, 0.0)
        assert result.recommended_qty == 0
        assert result.position_value == 0.0

    def test_zero_portfolio_returns_zero(self):
        result = self.sizer.calculate("SBER", 0, 0.8, 5.0, 250.0)
        assert result.recommended_qty == 0

    def test_kelly_criterion_positive(self):
        k = PositionSizer.kelly_criterion(0.6, 2.0, 1.0)
        assert k > 0

    def test_kelly_criterion_zero_loss(self):
        k = PositionSizer.kelly_criterion(0.6, 2.0, 0.0)
        assert k == 0.0

    def test_volatility_based_zero_atr(self):
        result = self.sizer.volatility_based(1_000_000, 0.0)
        assert result == 0

    def test_lot_size_rounding(self):
        config = PositionSizerConfig(lot_size=10)
        sizer = PositionSizer(config)
        result = sizer.calculate("SBER", 1_000_000, 0.5, 5.0, 100.0)
        assert result.recommended_qty % 10 == 0 or result.recommended_qty == 1

    def test_portfolio_fraction_within_bounds(self):
        result = self.sizer.calculate("SBER", 1_000_000, 0.5, 5.0, 250.0)
        assert 0 <= result.portfolio_fraction <= 100
