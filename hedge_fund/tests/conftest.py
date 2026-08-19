import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_config():
    return {
        "max_drawdown_pct": 5.0,
        "max_position_concentration_pct": 15.0,
        "max_daily_loss": 50000.0,
        "max_open_positions": 10,
        "max_total_exposure_pct": 90.0,
        "portfolio_value": 1_000_000.0,
    }


@pytest.fixture
def mock_database():
    db = MagicMock()
    db.execute = AsyncMock(return_value=[])
    db.fetch_one = AsyncMock(return_value=None)
    db.fetch_all = AsyncMock(return_value=[])
    return db


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
