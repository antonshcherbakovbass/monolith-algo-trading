import pytest

from hedge_fund.risk.daily_loss_lock import DailyLossLock


class TestDailyLossLock:
    def setup_method(self):
        self.lock = DailyLossLock(max_daily_loss_pct=2.0, portfolio_value=1_000_000)

    def test_not_locked_initially(self):
        assert self.lock.is_locked() is False

    def test_remaining_budget_initial(self):
        assert self.lock.get_remaining_budget() == 20_000.0

    def test_gradual_loss_accumulation(self):
        self.lock.record_loss(5_000)
        assert self.lock.is_locked() is False
        assert self.lock.get_remaining_budget() == 15_000.0

    def test_lock_triggers_at_limit(self):
        self.lock.record_loss(20_000)
        assert self.lock.is_locked() is True

    def test_lock_triggers_above_limit(self):
        self.lock.record_loss(10_000)
        self.lock.record_loss(15_000)
        assert self.lock.is_locked() is True

    def test_reset_clears_lock(self):
        self.lock.record_loss(25_000)
        assert self.lock.is_locked() is True
        self.lock.reset()
        assert self.lock.is_locked() is False
        assert self.lock.get_remaining_budget() == 20_000.0

    def test_remaining_budget_never_negative(self):
        self.lock.record_loss(30_000)
        assert self.lock.get_remaining_budget() == 0.0

    def test_negative_loss_ignored(self):
        self.lock.record_loss(-5_000)
        assert self.lock.get_remaining_budget() == 20_000.0

    def test_lock_reason_empty_when_unlocked(self):
        assert self.lock.lock_reason() == ""

    def test_lock_reason_non_empty_when_locked(self):
        self.lock.record_loss(25_000)
        assert len(self.lock.lock_reason()) > 0
