import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from hedge_fund.risk.risk_limits import RiskLimits, RiskLimitsConfig


@dataclass
class FakePosition:
    ticker: str
    qty: int
    current_price: float


@dataclass
class FakeOrder:
    ticker: str
    side: str
    qty: int
    price: float


@dataclass
class FakeSnapshot:
    daily_pnl: float


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def risk_limits(mock_db):
    config = RiskLimitsConfig(
        max_drawdown_pct=5.0,
        max_position_concentration_pct=15.0,
        max_daily_loss=50000.0,
        max_open_positions=10,
        max_total_exposure_pct=90.0,
        portfolio_value=1_000_000.0,
    )
    with patch("hedge_fund.risk.risk_limits.PositionRepository") as pos_repo, \
         patch("hedge_fund.risk.risk_limits.PortfolioRepository") as port_repo, \
         patch("hedge_fund.risk.risk_limits.OrderRepository"):
        pos_repo.return_value.get_all_positions = AsyncMock(return_value=[])
        port_repo.return_value.get_drawdown = AsyncMock(return_value=0.0)
        port_repo.return_value.get_history = AsyncMock(return_value=[])
        rl = RiskLimits(config, mock_db)
        rl._position_repo = pos_repo.return_value
        rl._portfolio_repo = port_repo.return_value
        return rl


@pytest.mark.asyncio
async def test_order_approved_within_limits(risk_limits):
    risk_limits._position_repo.get_all_positions = AsyncMock(return_value=[])
    risk_limits._portfolio_repo.get_drawdown = AsyncMock(return_value=1.0)
    risk_limits._portfolio_repo.get_history = AsyncMock(return_value=[FakeSnapshot(daily_pnl=0.0)])

    order = FakeOrder(ticker="SBER", side="buy", qty=10, price=250.0)
    result = await risk_limits.check_order(order)
    assert result.approved is True
    assert len(result.reasons) == 0


@pytest.mark.asyncio
async def test_rejected_max_drawdown_exceeded(risk_limits):
    risk_limits._position_repo.get_all_positions = AsyncMock(return_value=[])
    risk_limits._portfolio_repo.get_drawdown = AsyncMock(return_value=6.0)
    risk_limits._portfolio_repo.get_history = AsyncMock(return_value=[FakeSnapshot(daily_pnl=0.0)])

    order = FakeOrder(ticker="SBER", side="buy", qty=10, price=250.0)
    result = await risk_limits.check_order(order)
    assert result.approved is False
    assert any("drawdown" in r.lower() for r in result.reasons)


@pytest.mark.asyncio
async def test_rejected_daily_loss_exceeded(risk_limits):
    risk_limits._position_repo.get_all_positions = AsyncMock(return_value=[])
    risk_limits._portfolio_repo.get_drawdown = AsyncMock(return_value=0.0)
    risk_limits._portfolio_repo.get_history = AsyncMock(return_value=[FakeSnapshot(daily_pnl=-60000.0)])

    order = FakeOrder(ticker="SBER", side="buy", qty=10, price=250.0)
    result = await risk_limits.check_order(order)
    assert result.approved is False
    assert any("daily loss" in r.lower() for r in result.reasons)


@pytest.mark.asyncio
async def test_rejected_position_concentration(risk_limits):
    risk_limits._position_repo.get_all_positions = AsyncMock(return_value=[])
    risk_limits._portfolio_repo.get_drawdown = AsyncMock(return_value=0.0)
    risk_limits._portfolio_repo.get_history = AsyncMock(return_value=[FakeSnapshot(daily_pnl=0.0)])

    order = FakeOrder(ticker="SBER", side="buy", qty=1000, price=200.0)
    result = await risk_limits.check_order(order)
    assert result.approved is False
    assert any("concentration" in r.lower() for r in result.reasons)


@pytest.mark.asyncio
async def test_rejected_max_open_positions(risk_limits):
    positions = [FakePosition(f"T{i}", 10, 100.0) for i in range(10)]
    risk_limits._position_repo.get_all_positions = AsyncMock(return_value=positions)
    risk_limits._portfolio_repo.get_drawdown = AsyncMock(return_value=0.0)
    risk_limits._portfolio_repo.get_history = AsyncMock(return_value=[FakeSnapshot(daily_pnl=0.0)])

    order = FakeOrder(ticker="NEW", side="buy", qty=1, price=100.0)
    result = await risk_limits.check_order(order)
    assert result.approved is False
    assert any("open positions" in r.lower() for r in result.reasons)


@pytest.mark.asyncio
async def test_boundary_drawdown_at_limit(risk_limits):
    risk_limits._position_repo.get_all_positions = AsyncMock(return_value=[])
    risk_limits._portfolio_repo.get_drawdown = AsyncMock(return_value=5.0)
    risk_limits._portfolio_repo.get_history = AsyncMock(return_value=[FakeSnapshot(daily_pnl=0.0)])

    order = FakeOrder(ticker="SBER", side="buy", qty=1, price=100.0)
    result = await risk_limits.check_order(order)
    assert result.approved is False
