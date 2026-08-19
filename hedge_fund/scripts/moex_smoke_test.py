"""Quick MOEX connectivity test — run: python -u -m hedge_fund.scripts.moex_smoke_test"""
from __future__ import annotations

import asyncio
import sys

from hedge_fund.data.moex_loader import MOEXDataLoader


async def main() -> int:
    print("MOEX smoke test: SBER from 2024-01-01...", flush=True)
    loader = MOEXDataLoader()
    try:
        df = await loader.fetch_candles("SBER", start_date="2024-01-01")
    except TimeoutError as exc:
        print(f"TIMEOUT: {exc}", flush=True)
        print("Проверьте: VPN выключен, https://iss.moex.com в браузере, файрвол", flush=True)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        return 1

    print(f"OK: {len(df)} rows", flush=True)
    if len(df):
        print(f"  first: {df.iloc[0]['datetime']}  last: {df.iloc[-1]['datetime']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
