import pytest

from hedge_fund.core.portfolio_health import PortfolioHealth


class TestPortfolioHealth:
    def setup_method(self):
        self.ph = PortfolioHealth()

    def test_green_conditions(self):
        color, emoji, _ = self.ph.calculate_health(
            daily_pnl_pct=0.5, drawdown_pct=1.0, diversification_score=0.8,
            win_rate=60.0, risk_utilization_pct=40.0
        )
        assert color == "green"
        assert emoji == "🟢"

    def test_red_high_drawdown(self):
        color, emoji, explanation = self.ph.calculate_health(
            daily_pnl_pct=0.0, drawdown_pct=5.0, diversification_score=0.8,
            win_rate=60.0, risk_utilization_pct=40.0
        )
        assert color == "red"
        assert "просадка" in explanation

    def test_red_high_risk_utilization(self):
        color, _, _ = self.ph.calculate_health(
            daily_pnl_pct=0.0, drawdown_pct=1.0, diversification_score=0.8,
            win_rate=60.0, risk_utilization_pct=85.0
        )
        assert color == "red"

    def test_red_large_daily_loss(self):
        color, _, _ = self.ph.calculate_health(
            daily_pnl_pct=-2.0, drawdown_pct=1.0, diversification_score=0.8,
            win_rate=60.0, risk_utilization_pct=40.0
        )
        assert color == "red"

    def test_yellow_moderate_drawdown(self):
        color, emoji, _ = self.ph.calculate_health(
            daily_pnl_pct=0.0, drawdown_pct=2.5, diversification_score=0.8,
            win_rate=60.0, risk_utilization_pct=50.0
        )
        assert color == "yellow"
        assert emoji == "🟡"

    def test_yellow_low_win_rate(self):
        color, _, _ = self.ph.calculate_health(
            daily_pnl_pct=0.0, drawdown_pct=1.0, diversification_score=0.8,
            win_rate=45.0, risk_utilization_pct=40.0
        )
        assert color == "yellow"

    def test_boundary_drawdown_exactly_4(self):
        color, _, _ = self.ph.calculate_health(
            daily_pnl_pct=0.0, drawdown_pct=4.0, diversification_score=0.8,
            win_rate=60.0, risk_utilization_pct=40.0
        )
        assert color == "red"

    def test_boundary_risk_util_exactly_80(self):
        color, _, _ = self.ph.calculate_health(
            daily_pnl_pct=0.0, drawdown_pct=1.0, diversification_score=0.8,
            win_rate=60.0, risk_utilization_pct=80.0
        )
        assert color == "red"
