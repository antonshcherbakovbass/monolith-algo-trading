# Deployment Guide — MONOLITH Algo Trading Platform

## What this is

MONOLITH is an **algorithmic trading platform** for MOEX — multi-agent, paper/live modes, ML inference, backtesting. It is **not** a licensed hedge fund product.

---

## 1. Git setup

Git is required for version control. On Windows:

```powershell
winget install Git.Git
# Restart terminal, then:
.\scripts\init_git.ps1
```

The script initializes the repo and creates structured commits. For a remote on Cursor (macOS/Linux/WSL):

```bash
origin auth login
origin repo create monolith-algo-trading
git remote add origin <url-from-create>
git push -u origin main
```

On native Windows, use GitHub/GitLab manually or WSL for Cursor-hosted repos.

---

## 2. Environment variables

```powershell
copy .env.example .env
# Edit .env — never commit it
```

Key variables:

| Variable | Purpose |
|----------|---------|
| `MONOLITH_MODE` | `paper` or `live` |
| `TINKOFF_TOKEN` | Tinkoff Invest API token |
| `TELEGRAM_TOKEN` | Telegram bot token |
| `QUIK_HOST` / `QUIK_PORT` | QUIK LUA bridge |
| `DATABASE_URL` | SQLite/Postgres URL |
| `ML_AUTO_RETRAIN` | Enable scheduled retraining |

Config file `hedge_fund/config/settings.yaml` is the base; `.env` overrides secrets.

---

## 3. ML models

Bootstrap models (synthetic, offline — for dev/CI):

```bash
python -m hedge_fund.scripts.bootstrap_models
```

Train on real MOEX data:

```bash
python -m hedge_fund.ml.train_pipeline --source moex --tickers SBER GAZP LKOH
```

Artifacts in `hedge_fund/ml/models/`:

- `scalping_latest.pkl` — direction classifier
- `swing_latest.pkl` — return regressor
- `baseline_stats.json` — drift monitoring baseline
- `manifest.json` — training metadata

Drift is checked automatically during inference. Threshold: `ML_DRIFT_PSI_THRESHOLD` (default 0.2).

---

## 4. Live smoke tests (read-only)

Verifies broker connectivity without placing orders:

```bash
python -m hedge_fund.scripts.live_smoke_test --broker quik
python -m hedge_fund.scripts.live_smoke_test --broker tinkoff
python -m hedge_fund.scripts.live_smoke_test --broker all --json
```

Requirements:

- **QUIK**: LUA script running, bridge on `QUIK_HOST:QUIK_PORT`
- **Tinkoff**: `TINKOFF_TOKEN` in `.env`, `pip install tinkoff-investments`

---

## 5. Docker

```bash
copy .env.example .env
docker compose up -d monolith
```

Logs: `docker compose logs -f monolith`

One-off backtest:

```bash
docker compose --profile tools run backtest
```

Note: QUIK runs on the host — container connects via `host.docker.internal`. Ollama same.

---

## 6. Run locally (no Docker)

```bash
pip install -r hedge_fund/requirements.txt
python -m hedge_fund.scripts.bootstrap_models
python -m hedge_fund.main --no-gui --mode paper
```

---

## 7. Production checklist

- [ ] Git repo + remote configured
- [ ] `.env` with real tokens (not in git)
- [ ] Models trained on MOEX data (`--source moex`)
- [ ] Smoke tests pass for your broker
- [ ] Paper trading for ≥2 weeks before live
- [ ] `MONOLITH_MODE=live` only after risk acceptance
- [ ] Telegram alerts configured
- [ ] Daily backup of `hedge_fund/config/` and DB

---

## 8. Commands reference

| Command | Description |
|---------|-------------|
| `python -m hedge_fund.main --no-gui --mode paper` | Start platform |
| `python -m hedge_fund.backtesting --strategy mean_reversion ...` | Backtest |
| `python -m hedge_fund.ml.train_pipeline --source auto` | Train ML |
| `python -m hedge_fund.scripts.live_smoke_test --broker all` | Broker check |
| `python -m pytest hedge_fund/tests/ -q` | Tests |
