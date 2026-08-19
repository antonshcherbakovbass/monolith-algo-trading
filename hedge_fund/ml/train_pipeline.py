"""End-to-end ML training — thin CLI wrapper around unified pipeline.

Usage:
    python -m hedge_fund.ml.train_pipeline
    python -m hedge_fund.ml.train_pipeline --source moex --tickers SBER GAZP
    python -m hedge_fund.ml.train_pipeline --source synthetic
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from ..utils.logger import get_logger
from .pipeline import DEFAULT_TICKERS, run_ml_pipeline

log = get_logger("ml.train_pipeline")


async def run_training_pipeline(
    tickers: list[str] | None = None,
    start_date: str = "2022-01-01",
    model_dir: str = "hedge_fund/ml/models",
    source: str = "auto",
    min_samples: int = 500,
) -> dict[str, Any]:
    """Train scalping + swing models via unified pipeline."""
    result = await run_ml_pipeline(
        tickers=tickers or DEFAULT_TICKERS,
        models_dir=model_dir,
        min_samples=min_samples,
        start_date=start_date,
        source=source,
    )
    if "error" in result:
        log.error("Training failed: {}", result["error"])
        return result

    log.info("=== Training Report ===")
    log.info("  source: {}", result.get("source"))
    log.info("  samples: {}", result.get("samples"))
    for model in ("scalping", "swing"):
        metrics = result.get(model, {})
        if metrics:
            acc = metrics.get("accuracy_mean", metrics.get("neg_mse_mean", "n/a"))
            log.info("  {}: {}", model, acc)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="MONOLITH ML training pipeline")
    parser.add_argument("--tickers", nargs="+", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--model-dir", default="hedge_fund/ml/models")
    parser.add_argument(
        "--source",
        choices=["auto", "db", "moex", "synthetic"],
        default="auto",
        help="Data source (auto tries db → moex → synthetic)",
    )
    parser.add_argument("--min-samples", type=int, default=500)
    args = parser.parse_args()

    asyncio.run(
        run_training_pipeline(
            tickers=args.tickers,
            start_date=args.start_date,
            model_dir=args.model_dir,
            source=args.source,
            min_samples=args.min_samples,
        )
    )


if __name__ == "__main__":
    main()
