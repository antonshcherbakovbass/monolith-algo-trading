"""Unified ML training pipeline — single entry point for all training paths."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..data.moex_loader import MOEXDataLoader
from ..storage.database import Database
from ..utils.logger import get_logger
from .drift_monitor import DriftMonitor
from .features import FeatureGenerator
from .models import ScalpingModel, SwingModel

log = get_logger("ml.pipeline")

DEFAULT_TICKERS = ["SBER", "GAZP", "LKOH", "ROSN", "GMKN"]
CLASS_THRESHOLD = 0.002


def build_labels(
    close: pd.Series,
    features_index: pd.Index,
    threshold: float = CLASS_THRESHOLD,
) -> tuple[np.ndarray, np.ndarray]:
    """Build classification (up/flat/down) and regression (forward return) labels."""
    forward_return = close.pct_change(5).shift(-5)
    forward_return = forward_return.loc[features_index]
    y_cls = np.where(
        forward_return > threshold,
        0,
        np.where(forward_return < -threshold, 1, 2),
    ).astype(np.int64)
    y_reg = forward_return.fillna(0).values.astype(np.float32)
    return y_cls, y_reg


def prepare_features_from_frames(
    frames: list[pd.DataFrame],
    min_samples: int = 500,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, FeatureGenerator, list[str]]:
    """Combine OHLCV frames → feature matrix + labels."""
    if not frames:
        raise ValueError("No candle frames provided")

    combined = pd.concat([f.reset_index(drop=True) for f in frames], ignore_index=True)
    if len(combined) < min_samples:
        raise ValueError(f"Not enough samples: {len(combined)} < {min_samples}")

    feature_gen = FeatureGenerator()
    features_df = feature_gen.generate(combined)
    features_df = feature_gen.normalize(features_df).dropna()

    y_cls, y_reg = build_labels(combined["close"], features_df.index)
    X = features_df.values.astype(np.float32)

    valid = ~np.isnan(X).any(axis=1) & ~np.isnan(y_reg)
    X, y_cls, y_reg = X[valid], y_cls[valid], y_reg[valid]
    if len(X) < min_samples:
        raise ValueError(f"Not enough valid samples after features: {len(X)} < {min_samples}")

    feature_names = feature_gen.get_feature_names()
    log.info("Dataset ready: {} samples, {} features", len(X), X.shape[1])
    return X, y_cls, y_reg, feature_gen, feature_names


def walk_forward_validation(
    model: Any,
    X: np.ndarray,
    y: np.ndarray,
    folds: int = 5,
    is_classifier: bool = True,
) -> dict[str, float]:
    """Walk-forward cross-validation preserving temporal order."""
    n = len(X)
    fold_size = n // (folds + 1)
    metrics: list[float] = []

    for i in range(folds):
        train_end = fold_size * (i + 2)
        val_start = train_end
        val_end = min(val_start + fold_size, n)
        if val_end <= val_start:
            break

        X_train, y_train = X[:train_end], y[:train_end]
        X_val, y_val = X[val_start:val_end], y[val_start:val_end]

        model.train(X_train, y_train)
        preds = model.predict(X_val)

        if is_classifier:
            pred_classes = preds.argmax(axis=1) if preds.ndim > 1 else preds
            score = float(np.mean(pred_classes == y_val))
        else:
            score = float(-np.mean((preds - y_val) ** 2))
        metrics.append(score)

    avg = float(np.mean(metrics)) if metrics else 0.0
    std = float(np.std(metrics)) if metrics else 0.0
    metric_name = "accuracy" if is_classifier else "neg_mse"
    return {f"{metric_name}_mean": avg, f"{metric_name}_std": std}


def train_and_save_models(
    X: np.ndarray,
    y_cls: np.ndarray,
    y_reg: np.ndarray,
    models_dir: str | Path,
    feature_gen: FeatureGenerator,
    feature_names: list[str],
    source: str = "unknown",
) -> dict[str, Any]:
    """Train scalping + swing models, save artifacts + drift baseline."""
    models_path = Path(models_dir)
    models_path.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {
        "source": source,
        "samples": len(X),
        "features": X.shape[1],
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    scalping = ScalpingModel()
    scalping_metrics = walk_forward_validation(scalping, X, y_cls, is_classifier=True)
    scalping.train(X, y_cls)
    scalping.save(models_path / "scalping_latest.pkl")
    results["scalping"] = scalping_metrics

    swing = SwingModel()
    swing_metrics = walk_forward_validation(swing, X, y_reg, is_classifier=False)
    swing.train(X, y_reg)
    swing.save(models_path / "swing_latest.pkl")
    results["swing"] = swing_metrics

    # Drift baseline from training features
    features_df = pd.DataFrame(X, columns=feature_names[: X.shape[1]] if feature_names else None)
    monitor = DriftMonitor(models_path)
    monitor.save_baseline(features_df)

    manifest = {
        "version": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "source": source,
        "samples": len(X),
        "features": X.shape[1],
        "scalping": scalping_metrics,
        "swing": swing_metrics,
    }
    (models_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    log.info("Models saved to {} (source={})", models_path, source)
    return results


async def load_frames_from_db(
    tickers: list[str],
    db_url: str,
    min_count: int = 5000,
) -> list[pd.DataFrame]:
    from ..storage.timeseries import TimeSeriesStorage

    ts_store = TimeSeriesStorage(db_url)
    await ts_store.init()
    frames: list[pd.DataFrame] = []
    try:
        for ticker in tickers:
            candles = await ts_store.get_latest(ticker, "5m", count=min_count)
            if not candles:
                continue
            frames.append(pd.DataFrame([
                {
                    "timestamp": c.timestamp,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
                for c in candles
            ]))
    finally:
        await ts_store.close()
    return frames


async def load_frames_from_moex(
    tickers: list[str],
    start_date: str = "2022-01-01",
    *,
    quick: bool = False,
    use_cache: bool = True,
) -> list[pd.DataFrame]:
    """Load MOEX candles. quick=True: fast probe, abort after first ticker failure."""
    loader = MOEXDataLoader(use_cache=use_cache)
    frames: list[pd.DataFrame] = []
    log.info("MOEX download: {} tickers from {} (quick={})", len(tickers), start_date, quick)
    _cli_print(f"Загрузка MOEX: {', '.join(tickers)} с {start_date}...")
    for i, ticker in enumerate(tickers, 1):
        try:
            _cli_print(f"[{i}/{len(tickers)}] {ticker} — запрос к iss.moex.com...")
            df = await loader.fetch_candles(
                ticker, start_date=start_date, quick=quick, use_cache=use_cache,
            )
            if len(df) >= 100:
                frames.append(df)
                _cli_print(f"[{i}/{len(tickers)}] {ticker} — OK, {len(df)} свечей")
            else:
                log.warning("MOEX: {} — only {} rows, skipped", ticker, len(df))
                _cli_print(f"[{i}/{len(tickers)}] {ticker} — мало данных ({len(df)} строк)")
                if quick:
                    _cli_print("MOEX quick: прерываем — нет данных у первого тикера")
                    break
        except (TimeoutError, OSError, asyncio.TimeoutError) as exc:
            log.error("MOEX timeout for {}: {}", ticker, exc)
            _cli_print(f"[{i}/{len(tickers)}] {ticker} — недоступен: {exc}")
            if quick:
                _cli_print("MOEX quick: прерываем после ошибки первого тикера")
                break
        except Exception as exc:
            log.warning("MOEX fetch failed for {}: {}", ticker, exc)
            _cli_print(f"[{i}/{len(tickers)}] {ticker} — ошибка: {exc}")
            if quick:
                break
    return frames


def _cli_print(msg: str) -> None:
    """Immediate stdout for Windows cmd (works with python -u)."""
    print(msg, flush=True)


def load_frames_synthetic(n: int = 2500, seed: int = 42) -> list[pd.DataFrame]:
    """Generate synthetic OHLCV for bootstrap / CI when no market data available."""
    rng = np.random.default_rng(seed)
    base = 250.0 + np.cumsum(rng.normal(0, 0.3, n))
    df = pd.DataFrame({
        "open": base * 0.998,
        "high": base * 1.005,
        "low": base * 0.995,
        "close": base,
        "volume": rng.integers(10_000, 100_000, n),
    })
    return [df]


async def run_ml_pipeline(
    *,
    tickers: list[str] | None = None,
    models_dir: str = "hedge_fund/ml/models",
    min_samples: int = 500,
    start_date: str = "2022-01-01",
    source: str = "auto",
    db_url: str | None = None,
    db: Database | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Single training pipeline.

    source:
      - auto: DB → MOEX → synthetic
      - db: timeseries DB only
      - moex: MOEX ISS only
      - synthetic: bootstrap data only
    """
    tickers = tickers or DEFAULT_TICKERS
    frames: list[pd.DataFrame] = []
    used_source = source

    _cli_print(f"ML pipeline: source={source}, tickers={tickers}, start={start_date}")
    log.info("ML pipeline start: source={} tickers={}", source, tickers)

    if source in ("auto", "db") and db_url:
        try:
            frames = await load_frames_from_db(tickers, db_url)
            if frames:
                used_source = "db"
        except Exception as exc:
            log.warning("DB load failed: {}", exc)

    if not frames and source in ("auto", "moex"):
        moex_quick = source == "auto"
        if moex_quick:
            _cli_print("MOEX: быстрая проверка (до ~20 сек)...")
        else:
            _cli_print("Подключение к MOEX ISS (iss.moex.com)...")
        try:
            frames = await load_frames_from_moex(
                tickers, start_date, quick=moex_quick, use_cache=use_cache,
            )
            if frames:
                used_source = "moex"
        except Exception as exc:
            log.warning("MOEX load failed: {}", exc)
            _cli_print(f"MOEX недоступен: {exc}")

    if not frames and source in ("auto", "synthetic"):
        if source == "auto":
            _cli_print(
                "MOEX недоступен — обучение на synthetic данных.\n"
                "  Проверьте: интернет, VPN, антivirus (SSL), https://iss.moex.com\n"
                "  Для MOEX вручную: python -u -m hedge_fund.ml.train_pipeline --source moex --tickers SBER"
            )
        else:
            _cli_print("Генерация synthetic данных...")
        frames = load_frames_synthetic()
        used_source = "synthetic"

    if not frames and source == "moex":
        return {
            "error": (
                "no moex data — проверьте интернет, VPN/файрвол, "
                "откройте https://iss.moex.com в браузере"
            )
        }

    if not frames:
        return {"error": "no training data from any source"}

    try:
        X, y_cls, y_reg, feature_gen, feature_names = prepare_features_from_frames(
            frames, min_samples=min_samples
        )
    except ValueError as exc:
        return {"error": str(exc)}

    results = train_and_save_models(
        X, y_cls, y_reg, models_dir, feature_gen, feature_names, source=used_source
    )

    if db is not None:
        from .trainer import AutoTrainer

        trainer = AutoTrainer({"models_dir": models_dir}, db)
        await trainer.save_model_version("scalping", results.get("scalping", {}), "scalping_latest.pkl")
        await trainer.save_model_version("swing", results.get("swing", {}), "swing_latest.pkl")

    return results
