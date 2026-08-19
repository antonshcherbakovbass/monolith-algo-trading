"""Bootstrap ML models for first run / CI (synthetic data, no network).

Usage:
    python -m hedge_fund.scripts.bootstrap_models
"""

from __future__ import annotations

import asyncio
import sys

from hedge_fund.ml.pipeline import run_ml_pipeline


async def main() -> int:
    result = await run_ml_pipeline(
        source="synthetic",
        min_samples=500,
        models_dir="hedge_fund/ml/models",
    )
    if "error" in result:
        print(f"Bootstrap failed: {result['error']}", file=sys.stderr)
        return 1
    print(
        f"Bootstrap OK: source={result.get('source')} "
        f"samples={result.get('samples')} "
        f"scalping_acc={result.get('scalping', {}).get('accuracy_mean', 'n/a')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
