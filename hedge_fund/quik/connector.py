"""Async TCP client for QUIK LUA bridge.

Connects to the LUA TCP server, sends JSON commands, receives responses
and event pushes.  Supports request batching, priority queues, heartbeat
monitoring, connection state machine, circuit breaker, message framing,
graceful degradation, and auto-reconnect with exponential backoff + jitter.
"""

from __future__ import annotations

import asyncio
import enum
import random
import struct
import time
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

import orjson

from ..core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from ..core.graceful_degradation import ComponentStatus, GracefulDegradation
from ..utils.logger import get_logger

logger = get_logger("quik.connector")

# 4-byte big-endian length prefix for message framing
_HEADER_FMT = "!I"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)
_MAX_MSG_SIZE = 16 * 1024 * 1024  # 16 MiB safety cap


class Priority(enum.IntEnum):
    CRITICAL = 0   # orders, cancels
    NORMAL = 1     # quotes, orderbook
    LOW = 2        # info, metadata


class ConnectionState(str, enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class _PendingRequest:
    id: int
    method: str
    params: dict[str, Any]
    priority: Priority
    future: asyncio.Future[dict[str, Any]]
    created_at: float = field(default_factory=time.monotonic)
    timeout: float = 5.0


@dataclass
class ConnectorMetrics:
    """Snapshot of live connector metrics."""
    connection_state: str
    connected_since: float | None
    uptime_seconds: float
    reconnect_count: int
    total_requests: int
    total_responses: int
    total_errors: int
    heartbeat_failures: int
    latency_last_ms: float
    latency_avg_ms: float
    latency_p99_ms: float
    circuit_breaker: dict[str, Any]


class QuikConnector:
    """Async TCP client that talks to the QUIK LUA bridge.

    Enhancements over the basic version:
    * Connection state machine (DISCONNECTED → CONNECTING → CONNECTED → RECONNECTING)
    * Exponential backoff with jitter on reconnect
    * Heartbeat every *heartbeat_interval* seconds; 3 consecutive misses → reconnect
    * Per-request timeout (configurable, default 5 s)
    * Priority queue: CRITICAL > NORMAL > LOW
    * Circuit breaker integration
    * Message framing: length-prefixed messages for safe partial-read handling
    * Graceful degradation: block new orders while disconnected, keep tracking existing
    * Latency histogram & comprehensive metrics
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 34130,
        *,
        batch_window_ms: float = 100.0,
        heartbeat_interval: float = 5.0,
        heartbeat_max_misses: int = 3,
        reconnect_base_delay: float = 1.0,
        reconnect_max_delay: float = 60.0,
        default_request_timeout: float = 5.0,
        use_length_prefix: bool = False,
        degradation: GracefulDegradation | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._batch_window = batch_window_ms / 1000.0
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_max_misses = heartbeat_max_misses
        self._reconnect_base = reconnect_base_delay
        self._reconnect_max = reconnect_max_delay
        self._default_timeout = default_request_timeout
        self._use_length_prefix = use_length_prefix

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._state = ConnectionState.DISCONNECTED
        self._closing = False
        self._connected_since: float | None = None

        self._request_id = 0
        self._pending: dict[int, _PendingRequest] = {}
        self._batch_queue: list[_PendingRequest] = []
        self._lock = asyncio.Lock()

        self._on_quote: list[Callable[..., Coroutine[Any, Any, None]]] = []
        self._on_trade: list[Callable[..., Coroutine[Any, Any, None]]] = []
        self._on_order: list[Callable[..., Coroutine[Any, Any, None]]] = []
        self._on_trans_reply: list[Callable[..., Coroutine[Any, Any, None]]] = []

        self._tasks: list[asyncio.Task[None]] = []

        # Metrics
        self._reconnect_count = 0
        self._total_requests = 0
        self._total_responses = 0
        self._total_errors = 0
        self._heartbeat_failures = 0
        self._latency_samples: deque[float] = deque(maxlen=500)
        self._read_buffer = bytearray()

        # Circuit breaker for the send path
        self._circuit = CircuitBreaker(
            name="quik_send",
            failure_threshold=5,
            recovery_timeout=15.0,
        )

        # Graceful degradation registry
        self._degradation = degradation

    # ------------------------------------------------------------------
    # Connection state helpers
    # ------------------------------------------------------------------

    def _set_state(self, new: ConnectionState) -> None:
        old = self._state
        if old == new:
            return
        self._state = new
        logger.info("connection state: {} → {}", old.value, new.value)
        if self._degradation:
            if new == ConnectionState.CONNECTED:
                self._degradation.report_status(
                    "quik_connector", ComponentStatus.HEALTHY
                )
            elif new == ConnectionState.RECONNECTING:
                self._degradation.report_status(
                    "quik_connector", ComponentStatus.DEGRADED, "reconnecting"
                )
            elif new == ConnectionState.DISCONNECTED:
                self._degradation.report_status(
                    "quik_connector", ComponentStatus.FAILED, "disconnected"
                )

    # ------------------------------------------------------------------
    # Event registration
    # ------------------------------------------------------------------

    def on_quote(self, callback: Callable[..., Coroutine[Any, Any, None]]) -> None:
        self._on_quote.append(callback)

    def on_trade(self, callback: Callable[..., Coroutine[Any, Any, None]]) -> None:
        self._on_trade.append(callback)

    def on_order(self, callback: Callable[..., Coroutine[Any, Any, None]]) -> None:
        self._on_order.append(callback)

    def on_trans_reply(self, callback: Callable[..., Coroutine[Any, Any, None]]) -> None:
        self._on_trans_reply.append(callback)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> QuikConnector:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def connect(self) -> None:
        """Establish TCP connection and start background tasks."""
        await self._connect_once()
        self._tasks = [
            asyncio.create_task(self._read_loop(), name="quik-read"),
            asyncio.create_task(self._batch_loop(), name="quik-batch"),
            asyncio.create_task(self._heartbeat_loop(), name="quik-heartbeat"),
        ]

    async def _connect_once(self) -> None:
        delay = self._reconnect_base
        self._set_state(ConnectionState.CONNECTING)
        while not self._closing:
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port),
                    timeout=10.0,
                )
                self._set_state(ConnectionState.CONNECTED)
                self._connected_since = time.monotonic()
                self._read_buffer.clear()
                logger.info("connected to QUIK bridge at {}:{}", self._host, self._port)
                return
            except (OSError, asyncio.TimeoutError) as exc:
                jitter = random.uniform(0, delay * 0.3)
                wait = delay + jitter
                logger.warning("connection failed ({}), retrying in {:.1f}s", exc, wait)
                await asyncio.sleep(wait)
                delay = min(delay * 2, self._reconnect_max)
        raise ConnectionError("connector is closing")

    async def _reconnect(self) -> None:
        if self._state == ConnectionState.RECONNECTING:
            return
        self._set_state(ConnectionState.RECONNECTING)
        self._connected_since = None
        self._reconnect_count += 1
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._writer = None
        self._reader = None
        self._read_buffer.clear()
        for req in list(self._pending.values()):
            if not req.future.done():
                req.future.set_exception(ConnectionError("disconnected"))
        self._pending.clear()
        if not self._closing:
            await self._connect_once()

    async def close(self) -> None:
        """Gracefully shut down the connector."""
        self._closing = True
        self._set_state(ConnectionState.DISCONNECTED)
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

    @property
    def connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    @property
    def connection_state(self) -> ConnectionState:
        return self._state

    # ------------------------------------------------------------------
    # Sending requests
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _frame_message(self, payload: bytes) -> bytes:
        """Wrap *payload* with a length-prefix header if framing is enabled."""
        if self._use_length_prefix:
            return struct.pack(_HEADER_FMT, len(payload)) + payload
        return payload + b"\n"

    async def _send_raw(self, data: bytes) -> None:
        if not self._writer or self._state != ConnectionState.CONNECTED:
            raise ConnectionError("not connected")
        self._writer.write(data)
        await self._writer.drain()

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        priority: Priority = Priority.NORMAL,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a request and wait for its response.

        Raises ``CircuitBreakerOpen`` if too many consecutive send failures.
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        loop = asyncio.get_running_loop()
        req = _PendingRequest(
            id=self._next_id(),
            method=method,
            params=params or {},
            priority=priority,
            future=loop.create_future(),
            timeout=effective_timeout,
        )
        async with self._lock:
            self._batch_queue.append(req)
        self._total_requests += 1
        try:
            return await asyncio.wait_for(req.future, timeout=effective_timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req.id, None)
            self._total_errors += 1
            raise TimeoutError(f"request {method} (id={req.id}) timed out") from None

    async def _flush_batch(self) -> None:
        async with self._lock:
            if not self._batch_queue:
                return
            batch = sorted(self._batch_queue, key=lambda r: r.priority)
            self._batch_queue = []

        for req in batch:
            msg = orjson.dumps({"id": req.id, "method": req.method, "params": req.params})
            self._pending[req.id] = req
            try:
                await self._circuit.call(self._send_raw, self._frame_message(msg))
            except CircuitBreakerOpen:
                if not req.future.done():
                    req.future.set_exception(
                        ConnectionError("circuit breaker open, request rejected")
                    )
                self._pending.pop(req.id, None)
                self._total_errors += 1
            except ConnectionError:
                if not req.future.done():
                    req.future.set_exception(ConnectionError("send failed"))
                self._pending.pop(req.id, None)
                self._total_errors += 1

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    async def _batch_loop(self) -> None:
        while not self._closing:
            await asyncio.sleep(self._batch_window)
            try:
                await self._flush_batch()
            except Exception as exc:
                logger.error("batch flush error: {}", exc)

    async def _read_loop(self) -> None:
        while not self._closing:
            try:
                if not self._reader:
                    await asyncio.sleep(0.1)
                    continue
                if self._use_length_prefix:
                    await self._read_framed()
                else:
                    await self._read_line()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("read error: {}", exc)
                await self._reconnect()

    async def _read_line(self) -> None:
        assert self._reader is not None
        line = await self._reader.readline()
        if not line:
            logger.warning("connection closed by server")
            await self._reconnect()
            return
        self._handle_message(line)

    async def _read_framed(self) -> None:
        """Read length-prefixed messages, handling partial TCP reads."""
        assert self._reader is not None
        chunk = await self._reader.read(65536)
        if not chunk:
            logger.warning("connection closed by server")
            await self._reconnect()
            return
        self._read_buffer.extend(chunk)

        while len(self._read_buffer) >= _HEADER_SIZE:
            msg_len = struct.unpack_from(_HEADER_FMT, self._read_buffer)[0]
            if msg_len > _MAX_MSG_SIZE:
                logger.error("message too large ({} bytes), dropping connection", msg_len)
                self._read_buffer.clear()
                await self._reconnect()
                return
            total = _HEADER_SIZE + msg_len
            if len(self._read_buffer) < total:
                break
            payload = bytes(self._read_buffer[_HEADER_SIZE:total])
            del self._read_buffer[:total]
            self._handle_message(payload)

    async def _heartbeat_loop(self) -> None:
        consecutive_misses = 0
        while not self._closing:
            await asyncio.sleep(self._heartbeat_interval)
            if self._state != ConnectionState.CONNECTED:
                consecutive_misses = 0
                continue
            try:
                t0 = time.monotonic()
                await self.request("heartbeat", priority=Priority.CRITICAL, timeout=5.0)
                latency_ms = (time.monotonic() - t0) * 1000
                self._latency_samples.append(latency_ms)
                consecutive_misses = 0
            except Exception as exc:
                consecutive_misses += 1
                self._heartbeat_failures += 1
                logger.warning(
                    "heartbeat miss {}/{}: {}", consecutive_misses,
                    self._heartbeat_max_misses, exc,
                )
                if consecutive_misses >= self._heartbeat_max_misses:
                    logger.error("heartbeat lost, reconnecting")
                    consecutive_misses = 0
                    await self._reconnect()

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def _handle_message(self, raw: bytes) -> None:
        try:
            msg = orjson.loads(raw)
        except orjson.JSONDecodeError as exc:
            logger.error("invalid JSON from server: {}", exc)
            self._total_errors += 1
            return

        msg_type = msg.get("type")
        if msg_type == "response":
            self._total_responses += 1
            self._handle_response(msg)
        elif msg_type == "event":
            asyncio.create_task(self._handle_event(msg))
        else:
            logger.warning("unknown message type: {}", msg_type)

    def _handle_response(self, msg: dict[str, Any]) -> None:
        req_id = msg.get("id")
        req = self._pending.pop(req_id, None)
        if not req:
            logger.warning("response for unknown request id={}", req_id)
            return

        latency_ms = (time.monotonic() - req.created_at) * 1000
        self._latency_samples.append(latency_ms)

        if "error" in msg and msg["error"]:
            self._total_errors += 1
            if not req.future.done():
                req.future.set_exception(RuntimeError(msg["error"]))
        else:
            if not req.future.done():
                req.future.set_result(msg.get("result", {}))

    async def _handle_event(self, msg: dict[str, Any]) -> None:
        event = msg.get("event", "")
        data = msg.get("data", {})
        callbacks: list[Callable[..., Coroutine[Any, Any, None]]] = []
        if event == "quote":
            callbacks = self._on_quote
        elif event == "trade":
            callbacks = self._on_trade
        elif event == "order":
            callbacks = self._on_order
        elif event == "trans_reply":
            callbacks = self._on_trans_reply

        for cb in callbacks:
            try:
                await cb(data)
            except Exception as exc:
                logger.error("event callback error ({}): {}", event, exc)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ConnectorMetrics:
        uptime = 0.0
        if self._connected_since is not None:
            uptime = time.monotonic() - self._connected_since

        samples = list(self._latency_samples)
        avg = sum(samples) / len(samples) if samples else 0.0
        p99 = sorted(samples)[int(len(samples) * 0.99)] if samples else 0.0
        last = samples[-1] if samples else 0.0

        return ConnectorMetrics(
            connection_state=self._state.value,
            connected_since=self._connected_since,
            uptime_seconds=round(uptime, 2),
            reconnect_count=self._reconnect_count,
            total_requests=self._total_requests,
            total_responses=self._total_responses,
            total_errors=self._total_errors,
            heartbeat_failures=self._heartbeat_failures,
            latency_last_ms=round(last, 2),
            latency_avg_ms=round(avg, 2),
            latency_p99_ms=round(p99, 2),
            circuit_breaker=self._circuit.get_metrics(),
        )

    # ------------------------------------------------------------------
    # High-level API methods
    # ------------------------------------------------------------------

    async def subscribe(self, class_code: str, sec_code: str) -> dict[str, Any]:
        return await self.request(
            "subscribe",
            {"class_code": class_code, "sec_code": sec_code},
            priority=Priority.NORMAL,
        )

    async def unsubscribe(self, class_code: str, sec_code: str) -> dict[str, Any]:
        return await self.request(
            "unsubscribe",
            {"class_code": class_code, "sec_code": sec_code},
            priority=Priority.NORMAL,
        )

    async def get_quote(self, class_code: str, sec_code: str) -> dict[str, Any]:
        return await self.request(
            "get_quote",
            {"class_code": class_code, "sec_code": sec_code},
        )

    async def get_orderbook(self, class_code: str, sec_code: str) -> dict[str, Any]:
        return await self.request(
            "get_orderbook",
            {"class_code": class_code, "sec_code": sec_code},
        )

    async def get_candles(
        self,
        class_code: str,
        sec_code: str,
        interval: int = 1,
        count: int = 100,
    ) -> dict[str, Any]:
        return await self.request(
            "get_candles",
            {"class_code": class_code, "sec_code": sec_code, "interval": interval, "count": count},
            priority=Priority.LOW,
        )

    async def send_order(self, transaction: dict[str, Any]) -> dict[str, Any]:
        return await self.request("send_order", transaction, priority=Priority.CRITICAL)

    async def cancel_order(
        self,
        order_id: str,
        class_code: str,
        sec_code: str,
        *,
        trans_id: int | None = None,
        account: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "order_id": order_id,
            "class_code": class_code,
            "sec_code": sec_code,
        }
        if trans_id is not None:
            params["trans_id"] = trans_id
        if account is not None:
            params["account"] = account
        return await self.request("cancel_order", params, priority=Priority.CRITICAL)

    async def get_positions(
        self, account: str = "", firmid: str = ""
    ) -> dict[str, Any]:
        return await self.request("get_positions", {"account": account, "firmid": firmid})

    async def get_money(
        self,
        firmid: str = "",
        client_code: str = "",
        tag: str = "EQTV",
        limit_kind: int = 0,
    ) -> dict[str, Any]:
        return await self.request(
            "get_money",
            {"firmid": firmid, "client_code": client_code, "tag": tag, "limit_kind": limit_kind},
        )

    async def get_trades(self, account: str = "", count: int = 100) -> dict[str, Any]:
        return await self.request("get_trades", {"account": account, "count": count})

    async def get_info(self) -> dict[str, Any]:
        return await self.request("get_info", priority=Priority.LOW)
