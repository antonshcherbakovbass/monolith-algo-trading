"""Telegram reporting bot with rate limiting and command handlers."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any, Callable, Awaitable

import aiohttp

from ..utils.logger import get_logger

log = get_logger("reporting.telegram")

_MAX_MESSAGES_PER_MIN = 20


class TelegramReporter:
    """Sends formatted reports to Telegram with rate limiting."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._token = config.get("token", "")
        self._chat_id = config.get("chat_id", "")
        self._base_url = f"https://api.telegram.org/bot{self._token}"
        self._msg_timestamps: list[float] = []
        self._running = False
        self._poll_task: asyncio.Task[None] | None = None
        self._command_handlers: dict[str, Callable[..., Awaitable[str]]] = {}
        self._last_update_id = 0

        self._status_callback: Callable[[], Awaitable[dict[str, Any]]] | None = None
        self._pnl_callback: Callable[[], Awaitable[dict[str, Any]]] | None = None
        self._positions_callback: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None
        self._risk_callback: Callable[[], Awaitable[dict[str, Any]]] | None = None
        self._stop_callback: Callable[[], Awaitable[None]] | None = None
        self._start_callback: Callable[[], Awaitable[None]] | None = None

    def set_callbacks(
        self,
        status: Callable[[], Awaitable[dict[str, Any]]] | None = None,
        pnl: Callable[[], Awaitable[dict[str, Any]]] | None = None,
        positions: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None,
        risk: Callable[[], Awaitable[dict[str, Any]]] | None = None,
        stop: Callable[[], Awaitable[None]] | None = None,
        start: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._status_callback = status
        self._pnl_callback = pnl
        self._positions_callback = positions
        self._risk_callback = risk
        self._stop_callback = stop
        self._start_callback = start

    async def _rate_limit(self) -> None:
        now = time.time()
        self._msg_timestamps = [t for t in self._msg_timestamps if now - t < 60]
        if len(self._msg_timestamps) >= _MAX_MESSAGES_PER_MIN:
            wait = 60 - (now - self._msg_timestamps[0])
            if wait > 0:
                log.warning("Rate limit reached, waiting {:.1f}s", wait)
                await asyncio.sleep(wait)
        self._msg_timestamps.append(time.time())

    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        await self._rate_limit()
        url = f"{self._base_url}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": text, "parse_mode": parse_mode}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        log.error("Telegram send failed ({}): {}", resp.status, body)
                        return False
                    return True
        except Exception as exc:
            log.error("Telegram send error: {}", exc)
            return False

    async def send_trade_report(self, trade: dict[str, Any]) -> bool:
        pnl_emoji = "🟢" if trade.get("pnl", 0) >= 0 else "🔴"
        side_emoji = "📈" if trade.get("side") == "buy" else "📉"
        text = (
            f"{side_emoji} *Trade Executed*\n"
            f"Ticker: `{trade.get('ticker', '?')}`\n"
            f"Side: {trade.get('side', '?').upper()}\n"
            f"Qty: {trade.get('qty', 0)}\n"
            f"Price: {trade.get('price', 0):.2f}\n"
            f"Commission: {trade.get('commission', 0):.2f}\n"
            f"{pnl_emoji} PnL: {trade.get('pnl', 0):.2f}\n"
            f"Agent: {trade.get('agent', '?')}\n"
            f"Strategy: {trade.get('strategy', '?')}"
        )
        return await self.send_message(text)

    async def send_daily_report(self, report: dict[str, Any]) -> bool:
        pnl = report.get("daily_pnl", 0)
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        text = (
            f"📊 *Daily Report* — {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"💰 Portfolio: {report.get('portfolio_value', 0):,.0f} ₽\n"
            f"{pnl_emoji} Daily PnL: {pnl:+,.0f} ₽\n"
            f"📈 Total trades: {report.get('total_trades', 0)}\n"
            f"✅ Win rate: {report.get('win_rate', 0):.1%}\n"
            f"📉 Max drawdown: {report.get('max_drawdown', 0):.2f}%\n"
            f"⚡ Active agents: {report.get('active_agents', 0)}\n"
            f"📋 Open positions: {report.get('open_positions', 0)}"
        )
        return await self.send_message(text)

    async def send_risk_alert(self, alert: dict[str, Any]) -> bool:
        text = (
            f"🚨 *Risk Alert*\n\n"
            f"Level: {alert.get('level', 'WARNING')}\n"
            f"Message: {alert.get('message', '?')}\n"
            f"Metric: {alert.get('metric', '?')} = {alert.get('value', '?')}\n"
            f"Threshold: {alert.get('threshold', '?')}"
        )
        return await self.send_message(text)

    async def send_agent_status(self, agents: list[dict[str, Any]]) -> bool:
        lines = ["🤖 *Agent Status*\n"]
        for a in agents:
            status_emoji = "✅" if a.get("running") else "⛔"
            lines.append(
                f"{status_emoji} `{a.get('name', '?')}` — "
                f"signals: {a.get('signals', 0)}, "
                f"trades: {a.get('trades', 0)}"
            )
        return await self.send_message("\n".join(lines))

    # ------------------------------------------------------------------
    # Command polling
    # ------------------------------------------------------------------

    async def start_polling(self) -> None:
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        log.info("Telegram command polling started")

    async def stop_polling(self) -> None:
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        log.info("Telegram command polling stopped")

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._fetch_updates()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("Telegram poll error: {}", exc)
            await asyncio.sleep(2)

    async def _fetch_updates(self) -> None:
        url = f"{self._base_url}/getUpdates"
        params: dict[str, Any] = {"timeout": 10, "offset": self._last_update_id + 1}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        return
                    data = await resp.json()
        except Exception:
            return

        for update in data.get("result", []):
            self._last_update_id = update["update_id"]
            msg = update.get("message", {})
            text = msg.get("text", "")
            chat_id = str(msg.get("chat", {}).get("id", ""))

            if chat_id != str(self._chat_id):
                continue

            await self._handle_command(text)

    async def _handle_command(self, text: str) -> None:
        text = text.strip().lower()

        if text == "/status":
            if self._status_callback:
                data = await self._status_callback()
                lines = ["📋 *System Status*\n"]
                for k, v in data.items():
                    lines.append(f"  {k}: `{v}`")
                await self.send_message("\n".join(lines))
            else:
                await self.send_message("✅ System running")

        elif text == "/pnl":
            if self._pnl_callback:
                data = await self._pnl_callback()
                pnl = data.get("daily_pnl", 0)
                emoji = "🟢" if pnl >= 0 else "🔴"
                await self.send_message(
                    f"{emoji} *PnL*\n"
                    f"Daily: {pnl:+,.0f} ₽\n"
                    f"Total: {data.get('total_pnl', 0):+,.0f} ₽"
                )
            else:
                await self.send_message("PnL data unavailable")

        elif text == "/positions":
            if self._positions_callback:
                positions = await self._positions_callback()
                if not positions:
                    await self.send_message("📭 No open positions")
                else:
                    lines = ["📊 *Open Positions*\n"]
                    for p in positions:
                        emoji = "🟢" if p.get("unrealized_pnl", 0) >= 0 else "🔴"
                        lines.append(
                            f"{emoji} `{p.get('ticker')}` {p.get('qty')} @ {p.get('avg_price', 0):.2f}"
                        )
                    await self.send_message("\n".join(lines))
            else:
                await self.send_message("Position data unavailable")

        elif text == "/risk":
            if self._risk_callback:
                data = await self._risk_callback()
                await self.send_message(
                    f"🛡 *Risk Report*\n"
                    f"Exposure: {data.get('total_exposure', 0):,.0f} ₽\n"
                    f"Drawdown: {data.get('max_drawdown_current', 0):.2f}%\n"
                    f"Risk util: {data.get('risk_utilization_pct', 0):.1f}%\n"
                    f"Open pos: {data.get('open_positions_count', 0)}"
                )
            else:
                await self.send_message("Risk data unavailable")

        elif text == "/stop":
            await self.send_message("⛔ Stopping trading...")
            if self._stop_callback:
                await self._stop_callback()

        elif text == "/start":
            await self.send_message("▶️ Starting trading...")
            if self._start_callback:
                await self._start_callback()
