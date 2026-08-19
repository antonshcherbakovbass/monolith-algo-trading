"""FastAPI web dashboard with WebSocket live updates."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..utils.logger import get_logger

log = get_logger("reporting.dashboard")

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MONOLITH — LUX NOX Capital</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',system-ui,sans-serif;background:#0f1117;color:#e0e0e0}
  .header{background:#1a1d28;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #2a2d38}
  .header h1{font-size:1.3rem;color:#60a5fa}
  .header .status{color:#4ade80;font-size:.85rem}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px;padding:20px}
  .card{background:#1a1d28;border-radius:10px;padding:18px;border:1px solid #2a2d38}
  .card h2{font-size:.95rem;color:#94a3b8;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
  .metric{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #2a2d38}
  .metric:last-child{border:none}
  .metric .label{color:#94a3b8;font-size:.85rem}
  .metric .value{font-weight:600}
  .positive{color:#4ade80}.negative{color:#f87171}
  table{width:100%;border-collapse:collapse;font-size:.85rem}
  th{text-align:left;color:#94a3b8;padding:8px 6px;border-bottom:1px solid #2a2d38}
  td{padding:8px 6px;border-bottom:1px solid #1e2130}
  tr:hover{background:#1e2130}
  #ws-status{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}
  .connected{background:#4ade80}.disconnected{background:#f87171}
</style>
</head>
<body>
<div class="header">
  <h1>◇ LUX NOX Capital · MONOLITH ◇</h1>
  <div class="status"><span id="ws-status" class="disconnected"></span><span id="ws-text">Connecting...</span></div>
</div>
<div class="grid">
  <div class="card"><h2>💰 Portfolio</h2><div id="portfolio"></div></div>
  <div class="card"><h2>📊 Positions</h2><div id="positions"><table><thead><tr><th>Ticker</th><th>Qty</th><th>Avg Price</th><th>PnL</th></tr></thead><tbody id="pos-body"></tbody></table></div></div>
  <div class="card"><h2>📈 Recent Trades</h2><div id="trades"><table><thead><tr><th>Time</th><th>Ticker</th><th>Side</th><th>Qty</th><th>Price</th><th>PnL</th></tr></thead><tbody id="trade-body"></tbody></table></div></div>
  <div class="card"><h2>🤖 Agents</h2><div id="agents"></div></div>
  <div class="card"><h2>🛡️ Risk</h2><div id="risk"></div></div>
  <div class="card"><h2>💹 PnL</h2><div id="pnl"></div></div>
</div>
<script>
let ws;
function connect(){
  ws=new WebSocket(`ws://${location.host}/ws`);
  ws.onopen=()=>{document.getElementById('ws-status').className='connected';document.getElementById('ws-text').textContent='Live';};
  ws.onclose=()=>{document.getElementById('ws-status').className='disconnected';document.getElementById('ws-text').textContent='Reconnecting...';setTimeout(connect,3000);};
  ws.onmessage=(e)=>{const d=JSON.parse(e.data);if(d.type==='portfolio')renderPortfolio(d.data);if(d.type==='positions')renderPositions(d.data);if(d.type==='trades')renderTrades(d.data);if(d.type==='agents')renderAgents(d.data);if(d.type==='risk')renderRisk(d.data);if(d.type==='pnl')renderPnl(d.data);};
}
function renderPortfolio(d){let h='';for(const[k,v]of Object.entries(d)){const cls=typeof v==='number'&&v<0?'negative':'positive';h+=`<div class="metric"><span class="label">${k}</span><span class="value ${cls}">${typeof v==='number'?v.toLocaleString():v}</span></div>`;}document.getElementById('portfolio').innerHTML=h;}
function renderPositions(d){let h='';d.forEach(p=>{const cls=p.unrealized_pnl>=0?'positive':'negative';h+=`<tr><td>${p.ticker}</td><td>${p.qty}</td><td>${p.avg_price?.toFixed(2)}</td><td class="${cls}">${p.unrealized_pnl?.toFixed(0)}</td></tr>`;});document.getElementById('pos-body').innerHTML=h;}
function renderTrades(d){let h='';d.slice(0,20).forEach(t=>{const cls=t.pnl>=0?'positive':'negative';h+=`<tr><td>${t.time||''}</td><td>${t.ticker}</td><td>${t.side}</td><td>${t.qty}</td><td>${t.price?.toFixed(2)}</td><td class="${cls}">${t.pnl?.toFixed(0)}</td></tr>`;});document.getElementById('trade-body').innerHTML=h;}
function renderAgents(d){let h='';d.forEach(a=>{const em=a.running?'✅':'⛔';h+=`<div class="metric"><span class="label">${em} ${a.name}</span><span class="value">${a.signals||0} signals</span></div>`;});document.getElementById('agents').innerHTML=h;}
function renderRisk(d){let h='';for(const[k,v]of Object.entries(d)){h+=`<div class="metric"><span class="label">${k}</span><span class="value">${typeof v==='number'?v.toFixed(2):v}</span></div>`;}document.getElementById('risk').innerHTML=h;}
function renderPnl(d){let h='';for(const[k,v]of Object.entries(d)){const cls=typeof v==='number'&&v<0?'negative':'positive';h+=`<div class="metric"><span class="label">${k}</span><span class="value ${cls}">${typeof v==='number'?v.toLocaleString():v}</span></div>`;}document.getElementById('pnl').innerHTML=h;}
connect();
setInterval(()=>{if(ws&&ws.readyState===1)ws.send('ping');},5000);
</script>
</body>
</html>"""


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        log.info("WebSocket client connected (total={})", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        log.info("WebSocket client disconnected (total={})", len(self._connections))

    async def broadcast(self, msg_type: str, data: Any) -> None:
        payload = json.dumps({"type": msg_type, "data": data})
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)


class Dashboard:
    """FastAPI-based web dashboard."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        self._host = host
        self._port = port
        self.app = FastAPI(title="MONOLITH — LUX NOX Capital")
        self._ws_manager = ConnectionManager()
        self._data_callbacks: dict[str, Any] = {}
        self._broadcast_task: asyncio.Task[None] | None = None
        self._running = False
        self._setup_routes()

    def set_data_callbacks(self, callbacks: dict[str, Any]) -> None:
        self._data_callbacks = callbacks

    def _setup_routes(self) -> None:
        app = self.app
        ws_mgr = self._ws_manager
        dashboard = self

        @app.get("/", response_class=HTMLResponse)
        async def index(request: Request) -> HTMLResponse:
            return HTMLResponse(content=_INDEX_HTML)

        @app.get("/api/portfolio")
        async def api_portfolio() -> dict[str, Any]:
            cb = dashboard._data_callbacks.get("portfolio")
            return await cb() if cb else {}

        @app.get("/api/positions")
        async def api_positions() -> list[dict[str, Any]]:
            cb = dashboard._data_callbacks.get("positions")
            return await cb() if cb else []

        @app.get("/api/trades")
        async def api_trades() -> list[dict[str, Any]]:
            cb = dashboard._data_callbacks.get("trades")
            return await cb() if cb else []

        @app.get("/api/agents")
        async def api_agents() -> list[dict[str, Any]]:
            cb = dashboard._data_callbacks.get("agents")
            return await cb() if cb else []

        @app.get("/api/risk")
        async def api_risk() -> dict[str, Any]:
            cb = dashboard._data_callbacks.get("risk")
            return await cb() if cb else {}

        @app.get("/api/pnl")
        async def api_pnl() -> dict[str, Any]:
            cb = dashboard._data_callbacks.get("pnl")
            return await cb() if cb else {}

        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket) -> None:
            await ws_mgr.connect(ws)
            try:
                while True:
                    data = await ws.receive_text()
                    if data == "ping":
                        await ws.send_text(json.dumps({"type": "pong"}))
            except WebSocketDisconnect:
                ws_mgr.disconnect(ws)

    async def _broadcast_loop(self) -> None:
        while self._running:
            try:
                for key in ("portfolio", "positions", "trades", "agents", "risk", "pnl"):
                    cb = self._data_callbacks.get(key)
                    if cb:
                        data = await cb()
                        await self._ws_manager.broadcast(key, data)
            except Exception as exc:
                log.error("Broadcast error: {}", exc)
            await asyncio.sleep(2)

    async def start(self) -> None:
        import uvicorn

        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        config = uvicorn.Config(
            self.app, host=self._host, port=self._port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        log.info("Dashboard starting on http://{}:{}", self._host, self._port)
        await server.serve()

    async def stop(self) -> None:
        self._running = False
        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
