import pytest
from pydantic import ValidationError

from hedge_fund.core.models import (
    AlphaSignal,
    OrderProposal,
    Quote,
    Side,
    OrderType,
    InstrumentType,
)


class TestQuote:
    def test_valid_construction(self):
        q = Quote(ticker="SBER", bid=250.0, ask=250.5, last=250.2)
        assert q.ticker == "SBER"

    def test_spread_pct_auto_calculated(self):
        q = Quote(ticker="SBER", bid=200.0, ask=202.0)
        assert q.spread_pct == pytest.approx((202.0 - 200.0) / 200.0 * 100, rel=1e-4)

    def test_spread_pct_explicit_value_preserved(self):
        q = Quote(ticker="SBER", bid=200.0, ask=202.0, spread_pct=5.0)
        assert q.spread_pct == 5.0

    def test_spread_pct_zero_bid(self):
        q = Quote(ticker="SBER", bid=0.0, ask=10.0)
        assert q.spread_pct == 0.0

    def test_serialization_roundtrip(self):
        q = Quote(ticker="GAZP", bid=180.0, ask=180.5, last=180.3)
        data = q.model_dump()
        q2 = Quote(**data)
        assert q2.ticker == q.ticker
        assert q2.bid == q.bid


class TestAlphaSignal:
    def test_valid_signal(self):
        s = AlphaSignal(ticker="SBER", side=Side.BUY, confidence=0.8)
        assert s.confidence == 0.8

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            AlphaSignal(ticker="SBER", side=Side.BUY, confidence=1.5)

    def test_negative_confidence(self):
        with pytest.raises(ValidationError):
            AlphaSignal(ticker="SBER", side=Side.BUY, confidence=-0.1)


class TestOrderProposal:
    def test_valid_proposal(self):
        op = OrderProposal(ticker="SBER", side=Side.BUY, qty=10, price=250.0)
        assert op.qty == 10
        assert op.proposal_id != ""

    def test_invalid_qty_zero(self):
        with pytest.raises(ValidationError):
            OrderProposal(ticker="SBER", side=Side.BUY, qty=0, price=250.0)

    def test_invalid_side(self):
        with pytest.raises(ValidationError):
            OrderProposal(ticker="SBER", side="INVALID", qty=10, price=250.0)

    def test_is_profitable_after_fees(self):
        op = OrderProposal(ticker="SBER", side=Side.BUY, qty=10, price=250.0, expected_pnl=100.0)
        assert op.is_profitable_after_fees is True
