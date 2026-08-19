import pytest

from hedge_fund.risk.trade_confirmation import TradeConfirmation


class TestTradeConfirmation:
    def setup_method(self):
        self.tc = TradeConfirmation(threshold_rub=50_000)

    def test_below_threshold_no_confirm(self):
        assert self.tc.needs_confirmation(49_999) is False

    def test_above_threshold_needs_confirm(self):
        assert self.tc.needs_confirmation(60_000) is True

    def test_exactly_at_threshold(self):
        assert self.tc.needs_confirmation(50_000) is True

    def test_negative_value_uses_abs(self):
        assert self.tc.needs_confirmation(-60_000) is True

    def test_negative_below_threshold(self):
        assert self.tc.needs_confirmation(-30_000) is False

    def test_custom_threshold(self):
        tc = TradeConfirmation(threshold_rub=100_000)
        assert tc.needs_confirmation(99_999) is False
        assert tc.needs_confirmation(100_000) is True

    def test_zero_value(self):
        assert self.tc.needs_confirmation(0) is False
