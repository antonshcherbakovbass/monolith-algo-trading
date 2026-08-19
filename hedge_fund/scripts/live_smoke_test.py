"""Live connectivity smoke tests for QUIK and Tinkoff — read-only, no orders.

Usage:
    python -m hedge_fund.scripts.live_smoke_test --broker quik
    python -m hedge_fund.scripts.live_smoke_test --broker tinkoff
    python -m hedge_fund.scripts.live_smoke_test --broker all
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from hedge_fund.core.env_config import load_config, load_dotenv
from hedge_fund.utils.logger import get_logger

log = get_logger("scripts.live_smoke_test")


async def smoke_test_quik(host: str, port: int, timeout: float = 5.0) -> dict[str, Any]:
    from hedge_fund.quik.connector import QuikConnector

    result: dict[str, Any] = {"broker": "quik", "host": host, "port": port, "ok": False}
    connector = QuikConnector(host=host, port=port)
    try:
        await asyncio.wait_for(connector.connect(), timeout=timeout)
        info = await asyncio.wait_for(connector.request("get_info"), timeout=timeout)
        result["ok"] = True
        result["info"] = info
        log.info("QUIK smoke test passed: {}", info)
    except Exception as exc:
        result["error"] = str(exc)
        log.warning("QUIK smoke test failed: {}", exc)
    finally:
        try:
            await connector.close()
        except Exception:
            pass
    return result


async def smoke_test_tinkoff(token: str, sandbox: bool = True, timeout: float = 10.0) -> dict[str, Any]:
    from hedge_fund.brokers.tinkoff_broker import TinkoffBroker

    result: dict[str, Any] = {"broker": "tinkoff", "sandbox": sandbox, "ok": False}
    if not token or token in ("", "YOUR_TINKOFF_TOKEN"):
        result["error"] = "TINKOFF_TOKEN not set"
        result["skipped"] = True
        return result

    broker = TinkoffBroker(token=token, sandbox=sandbox)
    try:
        connected = await asyncio.wait_for(broker.connect(), timeout=timeout)
        result["connected"] = connected
        if not connected:
            result["error"] = "connect() returned False"
            return result
        portfolio = await asyncio.wait_for(broker.get_portfolio(), timeout=timeout)
        result["ok"] = True
        result["portfolio_value"] = round(portfolio.total_value, 2)
        result["positions"] = len(portfolio.positions)
        log.info("Tinkoff smoke test passed: portfolio={}", result["portfolio_value"])
    except ImportError:
        result["error"] = "tinkoff-investments package not installed"
        result["skipped"] = True
    except Exception as exc:
        result["error"] = str(exc)
        log.warning("Tinkoff smoke test failed: {}", exc)
    finally:
        try:
            await broker.disconnect()
        except Exception:
            pass
    return result


async def run_smoke_tests(broker: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    quik_cfg = config.get("quik", {})
    broker_cfg = config.get("broker", {})

    if broker in ("quik", "all"):
        results.append(await smoke_test_quik(
            host=quik_cfg.get("host", "127.0.0.1"),
            port=int(quik_cfg.get("port", 34130)),
        ))

    if broker in ("tinkoff", "all"):
        token = broker_cfg.get("tinkoff_token") or os.environ.get("TINKOFF_TOKEN", "")
        sandbox = bool(broker_cfg.get("tinkoff_sandbox", True))
        results.append(await smoke_test_tinkoff(token=token, sandbox=sandbox))

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live broker smoke tests (read-only)")
    parser.add_argument(
        "--broker",
        choices=["quik", "tinkoff", "all"],
        default="all",
        help="Which broker to test",
    )
    parser.add_argument("--config", default="hedge_fund/config/settings.yaml")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        config = load_config(args.config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    results = asyncio.run(run_smoke_tests(args.broker, config))

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            name = r.get("broker", "?")
            if r.get("skipped"):
                print(f"[SKIP] {name}: {r.get('error')}")
            elif r.get("ok"):
                print(f"[ OK ] {name}")
            else:
                print(f"[FAIL] {name}: {r.get('error')}")

    passed = sum(1 for r in results if r.get("ok"))
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = len(results) - passed - skipped

    print(f"\nResult: {passed} passed, {failed} failed, {skipped} skipped")
    # Exit 0 if at least one passed or all skipped (no credentials)
    if passed > 0:
        return 0
    if failed == 0 and skipped > 0:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
