"""Main entry point for the MONOLITH algo trading platform."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path
from typing import Any

import yaml

from hedge_fund.utils.logger import get_logger
from hedge_fund.core.env_config import load_config
from hedge_fund.storage.database import Database
from hedge_fund.storage.timeseries import TimeSeriesStorage
from hedge_fund.quik.connector import QuikConnector
from hedge_fund.quik.data_feed import DataFeed
from hedge_fund.quik.order_manager import OrderManager
from hedge_fund.risk.commission import CommissionCalculator, CommissionConfig
from hedge_fund.risk.risk_limits import RiskLimits, RiskLimitsConfig
from hedge_fund.risk.position_sizer import PositionSizer, PositionSizerConfig
from hedge_fund.reporting.telegram_bot import TelegramReporter
from hedge_fund.reporting.dashboard import Dashboard
from hedge_fund.core.event_bus import EventBus
from hedge_fund.agents.orchestrator import Orchestrator
from hedge_fund.agents.scalping_agent import ScalpingAgent
from hedge_fund.agents.day_trading_agent import DayTradingAgent
from hedge_fund.agents.long_term_agent import LongTermAgent
from hedge_fund.agents.news_agent import NewsAgent
from hedge_fund.agents.risk_agent import RiskAgent
from hedge_fund.agents.quant_agent import QuantAgent
from hedge_fund.agents.hedging_agent import HedgingAgent
from hedge_fund.agents.sre_agent import SREAgent
from hedge_fund.core.training_mode import TrainingMode
from hedge_fund.risk.daily_loss_lock import DailyLossLock
from hedge_fund.core.emergency_stop import EmergencyStop
from hedge_fund.core.config_backup import ConfigBackup
from hedge_fund.reporting.simple_summary import SimpleSummary
from hedge_fund.reporting.curator_alerts import CuratorAlerts
from hedge_fund.brokers.broker_factory import BrokerFactory
from hedge_fund.brokers.broker_data_feed import BrokerDataFeed
from hedge_fund.core.portfolio_health import PortfolioHealth
from hedge_fund.core.runtime_state import RuntimeState
from hedge_fund.core.config_loader import agents_as_dict, normalize_broker_name
from hedge_fund.core.execution_engine import ExecutionEngine
from hedge_fund.monitoring.health_check import HealthCheck, check_disk_space, check_memory_usage, check_ollama_reachable
from hedge_fund.monitoring.metrics import MetricsCollector
from hedge_fund.monitoring.alerting import AlertManager
from hedge_fund.ml.retrain_scheduler import MLRetrainScheduler

log = get_logger("main")


def _load_config(path: str) -> dict[str, Any]:
    return load_config(path)


async def _check_quik(connector: QuikConnector) -> bool:
    try:
        info = await asyncio.wait_for(connector.request("get_info"), timeout=5.0)
        log.info("QUIK connected: {}", info)
        return True
    except Exception as exc:
        log.error("QUIK connection check failed: {}", exc)
        return False


async def _check_ollama(config: dict[str, Any]) -> bool:
    import aiohttp

    url = config.get("ai", {}).get("base_url", "http://localhost:11434")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    log.info("Ollama reachable at {}", url)
                    return True
    except Exception as exc:
        log.warning("Ollama not reachable at {}: {}", url, exc)
    return False


async def _check_telegram(config: dict[str, Any]) -> bool:
    import aiohttp

    token = config.get("telegram", {}).get("token", "")
    if not token or token == "YOUR_TOKEN":
        log.warning("Telegram token not configured")
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    log.info("Telegram bot verified")
                    return True
    except Exception as exc:
        log.warning("Telegram check failed: {}", exc)
    return False


async def run(config: dict[str, Any], mode: str, no_dashboard: bool, agent_filter: list[str] | None) -> None:
    """Initialize and run all components."""
    paper = mode == "paper"
    log.info("Starting MONOLITH algo trading platform in {} mode", mode)

    db = Database(config.get("database", {}).get("url", "sqlite+aiosqlite:///hedge_fund.db"))
    await db.init()
    log.info("Database initialized")

    ts_store = TimeSeriesStorage()
    await ts_store.init()

    # --- Broker connector ---
    broker_cfg = config.get("broker", {})
    broker_name = normalize_broker_name(broker_cfg.get("name", "sber"))
    use_api_broker = BrokerFactory.is_api_broker(broker_name)

    broker_api = None
    connector: QuikConnector | None = None
    data_feed = None
    quik_ok = False

    if use_api_broker:
        try:
            broker_api = BrokerFactory.create(broker_name, config)
            quik_ok = await broker_api.connect()
            data_feed = BrokerDataFeed(broker_api)
            log.info("Connected via {} API", broker_name)
        except Exception as exc:
            log.error("API broker connection failed: {}", exc)
            if not paper:
                await db.close()
                return
    else:
        quik_cfg = config.get("quik", {})
        if paper:
            connector = None
            data_feed = None
            log.info("Paper mode without QUIK — using simulated order manager")
        else:
            connector = QuikConnector(
                host=quik_cfg.get("host", "127.0.0.1"),
                port=quik_cfg.get("port", 34130),
                batch_window_ms=quik_cfg.get("batch_window_ms", 100),
            )
            data_feed = DataFeed(connector)

    comm_cfg = config.get("commissions", {})
    stocks_cfg = comm_cfg.get("stocks", {})
    commission_calc = CommissionCalculator(CommissionConfig(
        broker_stock_pct=stocks_cfg.get("broker_fee_pct", 0.06),
        exchange_stock_pct=stocks_cfg.get("exchange_fee_pct", 0.01),
        clearing_stock_pct=stocks_cfg.get("clearing_fee_pct", 0.01),
    ))

    order_mgr = OrderManager(
        connector,
        paper_trading=paper,
        account=broker_cfg.get("account_id", ""),
        client_code=broker_cfg.get("client_code", ""),
        commission_calculator=commission_calc,
    )

    risk_cfg = config.get("risk", {})
    risk_limits = RiskLimits(
        RiskLimitsConfig(
            max_drawdown_pct=risk_cfg.get("max_drawdown_pct", 5.0),
            max_position_concentration_pct=risk_cfg.get("max_position_pct", 10.0),
            max_daily_loss=risk_cfg.get("max_daily_loss_pct", 2.0) * 10_000,
            max_open_positions=risk_cfg.get("max_open_positions", 20),
        ),
        db,
    )

    position_sizer = PositionSizer(PositionSizerConfig(
        max_position_pct=risk_cfg.get("max_position_pct", 10.0),
    ))

    # --- Safety modules ---
    safety_cfg = config.get("safety", {})
    training_mode = TrainingMode(training_period_days=safety_cfg.get("training_period_days", 14))

    default_portfolio = float(safety_cfg.get("default_portfolio_value", 1_000_000))
    daily_loss_lock = DailyLossLock(
        max_daily_loss_pct=safety_cfg.get("daily_loss_lock_pct", risk_cfg.get("max_daily_loss_pct", 2.0)),
        portfolio_value=default_portfolio,
    )

    async def _close_all_positions() -> None:
        log.critical("Closing all positions (emergency stop)")
        if broker_api is not None:
            await broker_api.close_all_positions()
        else:
            await order_mgr.close_all_positions()

    emergency_stop = EmergencyStop(close_all_callback=_close_all_positions)

    portfolio_health = PortfolioHealth()
    simple_summary = SimpleSummary()

    # Curator alerts
    curator_cfg = config.get("curator", {})
    curator: CuratorAlerts | None = None
    if curator_cfg.get("enabled") and curator_cfg.get("token"):
        curator = CuratorAlerts(
            curator_token=curator_cfg["token"],
            curator_chat_id=curator_cfg.get("chat_id", ""),
        )

    # Training mode check for live
    if not paper and training_mode.is_in_training() and not training_mode.has_accepted_risk():
        log.warning("Live mode requested during training period without risk acceptance — forcing paper mode")
        paper = True

    # --- Startup checks ---
    log.info("Running startup checks...")
    if connector is not None:
        await connector.connect()
        quik_ok = await _check_quik(connector)
        if not quik_ok and not paper:
            log.error("QUIK not reachable in live mode – aborting")
            await connector.close()
            await db.close()
            return
    elif use_api_broker and not quik_ok and not paper:
        log.error("Broker API not reachable in live mode – aborting")
        await db.close()
        return

    ollama_ok = await _check_ollama(config)
    telegram_ok = await _check_telegram(config)

    # --- Event Bus ---
    event_bus = EventBus()
    await event_bus.start()
    log.info("Event bus started")

    execution_engine = ExecutionEngine(
        order_manager=order_mgr if broker_api is None else None,
        broker_api=broker_api,
        position_sizer=position_sizer,
        daily_loss_lock=daily_loss_lock,
        emergency_stop=emergency_stop,
        event_bus=event_bus,
        config=config,
        default_portfolio_value=default_portfolio,
        paper=paper,
    )

    metrics = MetricsCollector()
    alert_manager = AlertManager()
    health_check = HealthCheck(check_interval=60.0)
    health_check.register_check("disk", check_disk_space, critical=False)
    health_check.register_check("memory", check_memory_usage, critical=False)
    health_check.register_check("ollama", check_ollama_reachable, critical=False)
    if connector is not None:
        health_check.register_check("quik", lambda: _check_quik(connector), critical=not paper)
    await health_check.start_periodic()

    # --- Create Agents ---
    agents_cfg = agents_as_dict(config)
    enabled_names: set[str] = set()
    for name, acfg in agents_cfg.items():
        if not acfg.get("enabled", True):
            continue
        if agent_filter and name not in agent_filter:
            continue
        enabled_names.add(name)

    agent_map: dict[str, Any] = {}
    agent_classes = {
        "orchestrator": Orchestrator,
        "scalping": ScalpingAgent,
        "day_trading": DayTradingAgent,
        "long_term": LongTermAgent,
        "news": NewsAgent,
        "risk": RiskAgent,
        "quant": QuantAgent,
        "hedging": HedgingAgent,
        "sre": SREAgent,
    }

    # Always create orchestrator and risk first
    orchestrator = Orchestrator(config, data_feed, order_mgr, db, execution_engine=execution_engine)
    agent_map["orchestrator"] = orchestrator

    for name in enabled_names:
        if name == "orchestrator":
            continue
        cls = agent_classes.get(name)
        if cls:
            agent = cls(config, data_feed, order_mgr, db)
            agent_map[name] = agent
            orchestrator.register_agent(agent)

    # Wire up SRE agent
    sre = agent_map.get("sre")
    if sre and isinstance(sre, SREAgent):
        sre.register_connector(connector)
        sre.register_event_bus(event_bus)
        sre.register_agents(agent_map)

    enabled_agents = [{"name": n, "enabled": True} for n in enabled_names]
    log.info("Enabled agents: {}", list(enabled_names))

    # --- Telegram ---
    telegram_reporter: TelegramReporter | None = None
    tg_cfg = config.get("telegram", {})
    if telegram_ok:
        telegram_reporter = TelegramReporter(tg_cfg)
        await telegram_reporter.start_polling()
        alert_manager.set_telegram_callback(telegram_reporter.send_message)
        await telegram_reporter.send_message(
            f"🚀 *MONOLITH System Started*\n"
            f"Mode: `{mode}`\n"
            f"Broker: `{broker_name}`\n"
            f"Agents: {len(enabled_agents)}\n"
            f"Connection: {'✅' if quik_ok or use_api_broker else '⚠️ paper/offline'}\n"
            f"Ollama: {'✅' if ollama_ok else '❌'}"
        )

    # --- Dashboard ---
    dashboard_task: asyncio.Task[None] | None = None
    dashboard: Dashboard | None = None
    if not no_dashboard:
        dashboard = Dashboard(port=8080)
        dashboard.set_data_callbacks({
            "portfolio": lambda: _get_portfolio_data(order_mgr, broker_api),
            "positions": lambda: _get_positions_data(order_mgr, broker_api),
            "trades": lambda: _get_trades_data(db),
            "agents": lambda: _get_agents_data(agent_map),
            "risk": lambda: _get_risk_data(risk_limits, daily_loss_lock),
            "pnl": lambda: _get_pnl_data(db),
        })
        dashboard_task = asyncio.create_task(dashboard.start())
        log.info("Dashboard task created")

    # Wire telegram to SRE and Risk agents
    if telegram_reporter:
        if sre and isinstance(sre, SREAgent):
            sre.register_telegram(telegram_reporter)
        risk_agent = agent_map.get("risk")
        if risk_agent and isinstance(risk_agent, RiskAgent):
            risk_agent.telegram_reporter = telegram_reporter

    # --- Start all agents ---
    for name, agent in agent_map.items():
        if name in enabled_names or name == "orchestrator":
            await agent.start()
            log.info("Agent {} started", name)

    # --- Subscribe instruments ---
    if data_feed is not None:
        instruments = config.get("instruments", {})
        for ticker in instruments.get("stocks", []):
            await data_feed.subscribe("TQBR", ticker)
        for ticker in instruments.get("futures", []):
            await data_feed.subscribe("RFUD", ticker)
    else:
        log.info("No live data feed — agents will run in offline/paper simulation mode")

    # --- Shutdown event ---
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        log.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig_name, _signal_handler)
        except NotImplementedError:
            pass

    log.info("System fully started – waiting for shutdown signal")

    async def _state_writer() -> None:
        while not shutdown_event.is_set():
            try:
                portfolio = await _get_portfolio_data(order_mgr, broker_api)
                pnl = await _get_pnl_data(db)
                positions = await _get_positions_data(order_mgr, broker_api)
                agents_data = await _get_agents_data(agent_map)
                recent = list(execution_engine.recent_executions)
                RuntimeState.write({
                    "mode": mode.upper(),
                    "connected": quik_ok or (broker_api is not None),
                    "broker": broker_name,
                    "portfolio_value": portfolio.get("total_value", default_portfolio),
                    "daily_pnl": pnl.get("daily_pnl", 0),
                    "positions": positions,
                    "trades": recent,
                    "agents": agents_data,
                    "events": [
                        f"{t.get('side', '?')} {t.get('ticker', '?')} x{t.get('qty', 0)}"
                        for t in recent[-10:]
                    ],
                    "daily_loss_locked": daily_loss_lock.is_locked(),
                    "emergency_stop": emergency_stop.is_active(),
                    "orders_executed": execution_engine.executed_count,
                })
            except Exception as exc:
                log.debug("runtime state write failed: {}", exc)
            await asyncio.sleep(3)

    async def _control_listener() -> None:
        while not shutdown_event.is_set():
            cmd = RuntimeState.read_control()
            if cmd and cmd.get("action") == "emergency_stop":
                emergency_stop.activate()
                RuntimeState.clear_control()
                if telegram_reporter:
                    await telegram_reporter.send_message("🚨 *Emergency stop activated from dashboard*")
            await asyncio.sleep(1)

    asyncio.create_task(_state_writer())
    asyncio.create_task(_control_listener())

    # --- ML auto-retrain scheduler ---
    ml_scheduler: MLRetrainScheduler | None = None
    ml_cfg = config.get("ml", {})
    if ml_cfg.get("auto_retrain_enabled", True):
        quant_agent = agent_map.get("quant")

        async def _on_ml_retrain_complete(result: dict[str, Any]) -> None:
            if quant_agent is not None and hasattr(quant_agent, "reload_ml_models"):
                reloaded = quant_agent.reload_ml_models()
                log.info("QuantAgent ML models reloaded: {}", reloaded)

        async def _ml_notify(msg: str) -> None:
            if telegram_reporter is not None:
                await telegram_reporter.send_message(msg)

        ml_scheduler = MLRetrainScheduler(
            config,
            db,
            on_complete=_on_ml_retrain_complete,
            notify=_ml_notify if telegram_reporter else None,
        )
        await ml_scheduler.start()

    await shutdown_event.wait()

    # --- Graceful shutdown ---
    log.info("Shutting down...")

    # Stop agents in reverse order
    for name in reversed(list(agent_map.keys())):
        try:
            await agent_map[name].stop()
        except Exception as e:
            log.warning("Error stopping agent {}: {}", name, e)

    await event_bus.stop()
    await health_check.stop()

    if ml_scheduler is not None:
        await ml_scheduler.stop()

    if telegram_reporter:
        await telegram_reporter.send_message("⛔ *System shutting down*")
        await telegram_reporter.stop_polling()

    if dashboard:
        await dashboard.stop()
    if dashboard_task and not dashboard_task.done():
        dashboard_task.cancel()
        try:
            await dashboard_task
        except (asyncio.CancelledError, Exception):
            pass

    if connector is not None:
        await connector.close()
    if broker_api is not None:
        await broker_api.disconnect()
    await ts_store.close()
    await db.close()
    log.info("Shutdown complete")


async def _get_portfolio_data(order_mgr: OrderManager, broker_api: Any = None) -> dict[str, Any]:
    try:
        if broker_api is not None:
            portfolio = await broker_api.get_portfolio()
            return {
                "total_value": round(portfolio.total_value, 2),
                "positions_count": len(portfolio.positions),
            }
        value = await order_mgr.get_portfolio_value()
        positions = await order_mgr.get_positions()
        return {
            "total_value": round(value, 2),
            "positions_count": len(positions),
        }
    except Exception:
        return {"total_value": 0, "positions_count": 0}


async def _get_positions_data(order_mgr: OrderManager, broker_api: Any = None) -> list[dict[str, Any]]:
    try:
        if broker_api is not None:
            positions = await broker_api.get_positions()
            return [
                {
                    "ticker": p.ticker,
                    "qty": p.qty,
                    "avg_price": p.avg_price,
                    "unrealized_pnl": p.unrealized_pnl,
                }
                for p in positions
            ]
        positions = await order_mgr.get_positions()
        return [
            {
                "ticker": p.sec_code,
                "qty": p.qty,
                "avg_price": p.avg_price,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in positions.values()
        ]
    except Exception:
        return []


async def _get_trades_data(db: Database) -> list[dict[str, Any]]:
    from hedge_fund.storage.database import TradeRepository

    try:
        repo = TradeRepository(db)
        trades = await repo.get_trades(limit=50)
        return [
            {
                "time": t.timestamp.strftime("%H:%M:%S") if t.timestamp else "",
                "ticker": t.ticker,
                "side": t.side,
                "qty": t.qty,
                "price": t.price,
                "pnl": t.pnl,
            }
            for t in trades
        ]
    except Exception:
        return []


async def _get_agents_data(agent_map: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for name, agent in agent_map.items():
        status = await agent.get_status()
        perf = getattr(agent, "performance", {})
        result.append({
            "name": name,
            "running": status.get("running", False),
            "signals": status.get("signals_processed", perf.get("trades", 0)),
            "trades": perf.get("trades", 0),
        })
    return result


async def _get_risk_data(risk_limits: RiskLimits, daily_loss_lock: DailyLossLock | None = None) -> dict[str, Any]:
    try:
        report = await risk_limits.get_risk_report()
        data = {
            "total_exposure": report.total_exposure,
            "max_drawdown_current": report.max_drawdown_current,
            "risk_utilization_pct": report.risk_utilization_pct,
            "open_positions_count": report.open_positions_count,
            "cash_available": report.cash_available,
        }
        if daily_loss_lock is not None:
            data["daily_loss_locked"] = daily_loss_lock.is_locked()
            data["daily_loss_remaining"] = daily_loss_lock.get_remaining_budget()
        return data
    except Exception:
        return {}


async def _get_pnl_data(db: Database) -> dict[str, Any]:
    from hedge_fund.storage.database import TradeRepository, PortfolioRepository

    try:
        trade_repo = TradeRepository(db)
        portfolio_repo = PortfolioRepository(db)
        total_pnl = await trade_repo.get_pnl()
        snapshots = await portfolio_repo.get_history(limit=1)
        daily_pnl = snapshots[0].daily_pnl if snapshots else 0.0
        return {"total_pnl": round(total_pnl, 2), "daily_pnl": round(daily_pnl, 2)}
    except Exception:
        return {"total_pnl": 0, "daily_pnl": 0}


def _needs_setup(config_path: Path) -> bool:
    """Check if the setup GUI should be shown."""
    if not config_path.exists():
        return True
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        token = cfg.get("telegram", {}).get("token", "")
        account = cfg.get("broker", {}).get("account_id", "")
        if token in ("", "YOUR_TOKEN") and account in ("", "YOUR_ACCOUNT_ID"):
            return True
    except Exception:
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="MONOLITH Trading System — LUX NOX Capital")
    parser.add_argument("--config", default="hedge_fund/config/settings.yaml", help="Path to config YAML")
    parser.add_argument("--mode", choices=["paper", "live"], default=None, help="Trading mode (overrides config)")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable web dashboard")
    parser.add_argument("--agents", nargs="*", default=None, help="Only run these agents")
    parser.add_argument("--no-gui", action="store_true", help="Skip setup GUI")
    parser.add_argument("--setup", action="store_true", help="Force show setup GUI")
    args = parser.parse_args()

    config_path = Path(args.config)

    # Auto-backup config before any changes
    config_backup = ConfigBackup(config_path)
    if config_path.exists():
        try:
            config_backup.create_backup()
        except Exception as e:
            print(f"Config backup warning: {e}")

    # Show setup GUI if needed
    if args.setup or (not args.no_gui and _needs_setup(config_path)):
        try:
            from hedge_fund.setup_gui import launch_setup
            config, action = launch_setup()
            if action != "run" or config is None:
                print("Setup cancelled.")
                sys.exit(0)
            mode = config.get("system", {}).get("mode", "paper")
        except ImportError:
            log.warning("GUI not available, falling back to CLI")
            if not config_path.exists():
                print(f"Config file not found: {config_path}", file=sys.stderr)
                sys.exit(1)
            config = _load_config(str(config_path))
            mode = args.mode or "paper"
        except Exception as e:
            log.warning("GUI error ({}), falling back to CLI", e)
            if not config_path.exists():
                print(f"Config file not found: {config_path}", file=sys.stderr)
                sys.exit(1)
            config = _load_config(str(config_path))
            mode = args.mode or "paper"
    else:
        if not config_path.exists():
            print(f"Config file not found: {config_path}", file=sys.stderr)
            sys.exit(1)
        config = _load_config(str(config_path))
        mode = args.mode or config.get("system", {}).get("mode", "paper")

    log.info("Config loaded, mode={}", mode)

    try:
        asyncio.run(run(config, mode, args.no_dashboard, args.agents))
    except KeyboardInterrupt:
        log.info("Interrupted by user")


if __name__ == "__main__":
    main()
