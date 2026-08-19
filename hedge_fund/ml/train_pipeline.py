"""End-to-end ML training — thin CLI wrapper around unified pipeline.

Usage:
    python -u -m hedge_fund.ml.train_pipeline
    python -u -m hedge_fund.ml.train_pipeline --source synthetic   # offline, ~30s
    python -u -m hedge_fund.ml.train_pipeline --source moex --tickers SBER --start-date 2024-01-01
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from ..utils.logger import get_logger
from .pipeline import DEFAULT_TICKERS, run_ml_pipeline

log = get_logger("ml.train_pipeline")


async def run_training_pipeline(
    tickers: list[str] | None = None,
    start_date: str = "2024-01-01",
    model_dir: str = "hedge_fund/ml/models",
    source: str = "auto",
    min_samples: int = 500,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Train scalping + swing models via unified pipeline."""
    print(
        f"Starting ML pipeline: source={source}, tickers={tickers or DEFAULT_TICKERS}, "
        f"start={start_date}",
        flush=True,
    )
    result = await run_ml_pipeline(
        tickers=tickers or DEFAULT_TICKERS,
        models_dir=model_dir,
        min_samples=min_samples,
        start_date=start_date,
        source=source,
        use_cache=use_cache,
    )
    if "error" in result:
        print(f"Training failed: {result['error']}", flush=True)
        log.error("Training failed: {}", result["error"])
        return result

    print("=== Training Report ===", flush=True)
    print(f"  source: {result.get('source')}", flush=True)
    print(f"  samples: {result.get('samples')}", flush=True)
    for model in ("scalping", "swing"):
        metrics = result.get(model, {})
        if metrics:
            acc = metrics.get("accuracy_mean", metrics.get("neg_mse_mean", "n/a"))
            print(f"  {model}: {acc}", flush=True)
            log.info("  {}: {}", model, acc)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="MONOLITH ML training pipeline")
    parser.add_argument("--tickers", nargs="+", default=None)
    parser.add_argument(
        "--start-date",
        default="2024-01-01",
        help="MOEX history start (use 2024-01-01 for quick test, 2022-01-01 for full)",
    )
    parser.add_argument("--model-dir", default="hedge_fund/ml/models")
    parser.add_argument(
        "--source",
        choices=["auto", "db", "moex", "synthetic"],
        default="auto",
        help=(
            "Data source: auto (db→moex quick→synthetic), moex, synthetic. "
            "If MOEX hangs/timeouts, use --source synthetic"
        ),
    )
    parser.add_argument("--min-samples", type=int, default=500)
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore local MOEX CSV cache in hedge_fund/data/historical/",
    )
    args = parser.parse_args()

    result = asyncio.run(
        run_training_pipeline(
            tickers=args.tickers,
            start_date=args.start_date,
            model_dir=args.model_dir,
            source=args.source,
            min_samples=args.min_samples,
            use_cache=not args.no_cache,
        )
    )
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
