import pytest

from hedge_fund.risk.commission import CommissionCalculator, CommissionConfig, InstrumentType


class TestCommissionCalculator:
    def setup_method(self):
        self.calc = CommissionCalculator()

    def test_stock_commission_basic(self):
        result = self.calc.calculate("SBER", "buy", 100, 250.0)
        turnover = 100 * 250.0
        expected_exchange = round(turnover * 0.01 / 100, 2)
        expected_broker = round(turnover * 0.06 / 100, 2)
        expected_clearing = round(turnover * 0.01 / 100, 2)
        assert result.exchange_fee == expected_exchange
        assert result.broker_fee == expected_broker
        assert result.clearing_fee == expected_clearing
        assert result.total == round(expected_exchange + expected_broker + expected_clearing, 2)

    def test_futures_commission_per_contract(self):
        result = self.calc.calculate("SiH5", "buy", 10, 90000.0, InstrumentType.FUTURES)
        assert result.exchange_fee == 10.0
        assert result.broker_fee == 5.0
        assert result.clearing_fee == 5.0
        assert result.total == 20.0

    def test_zero_qty_returns_zero(self):
        result = self.calc.calculate("SBER", "buy", 0, 250.0)
        assert result.total == 0.0
        assert result.exchange_fee == 0.0

    def test_custom_config(self):
        config = CommissionConfig(broker_stock_pct=0.10, exchange_stock_pct=0.02, clearing_stock_pct=0.02)
        calc = CommissionCalculator(config)
        result = calc.calculate("GAZP", "sell", 50, 180.0)
        turnover = 50 * 180.0
        assert result.broker_fee == round(turnover * 0.10 / 100, 2)
        assert result.exchange_fee == round(turnover * 0.02 / 100, 2)

    def test_total_equals_sum_of_parts(self):
        result = self.calc.calculate("LKOH", "buy", 5, 7000.0)
        assert result.total == round(result.exchange_fee + result.broker_fee + result.clearing_fee, 2)

    def test_is_profitable_true(self):
        assert self.calc.is_profitable(100.0, 110.0, 100, "SBER") is True

    def test_is_profitable_false_tiny_move(self):
        assert self.calc.is_profitable(100.0, 100.01, 1, "SBER") is False

    def test_min_profitable_move_zero_qty(self):
        assert self.calc.min_profitable_move("SBER", 0, 100.0) == 0.0

    def test_bond_commission(self):
        result = self.calc.calculate("OFZ26", "buy", 10, 1000.0, InstrumentType.BOND)
        turnover = 10 * 1000.0
        assert result.broker_fee == round(turnover * 0.06 / 100, 2)

    def test_etf_commission(self):
        result = self.calc.calculate("TMOS", "sell", 200, 5.5, InstrumentType.ETF)
        turnover = 200 * 5.5
        assert result.exchange_fee == round(turnover * 0.01 / 100, 2)
