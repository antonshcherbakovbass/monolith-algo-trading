"""Feature engineering for ML models."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..analysis.technical import rsi, macd, bollinger_bands, atr, stochastic, obv
from ..utils.logger import get_logger

log = get_logger("ml.features")


class FeatureGenerator:
    """Generates trading features from OHLCV + order-book data."""

    _RETURN_WINDOWS = (1, 5, 15, 60)
    _LAG_STEPS = (1, 2, 3)

    def __init__(self) -> None:
        self._feature_names: list[str] = []
        self._min_vals: pd.Series | None = None
        self._max_vals: pd.Series | None = None

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build the full feature matrix from an OHLCV DataFrame.

        Expected columns: open, high, low, close, volume.
        Optional columns: bid, ask, timestamp.
        """
        out = df.copy()

        for w in self._RETURN_WINDOWS:
            out[f"return_{w}"] = out["close"].pct_change(w)

        out["log_return"] = np.log(out["close"] / out["close"].shift(1))

        out["rsi"] = rsi(out["close"], period=14)

        _, _, macd_hist = macd(out["close"])
        out["macd_hist"] = macd_hist

        bb_upper, bb_middle, bb_lower = bollinger_bands(out["close"])
        bb_range = (bb_upper - bb_lower).replace(0, np.nan)
        out["bb_position"] = (out["close"] - bb_lower) / bb_range

        atr_vals = atr(out, period=14)
        atr_mean = atr_vals.rolling(60).mean().replace(0, np.nan)
        out["atr_ratio"] = atr_vals / atr_mean

        k, _d = stochastic(out)
        out["stochastic_k"] = k

        obv_vals = obv(out)
        out["obv_slope"] = obv_vals.diff(5) / 5.0

        vol_ma = out["volume"].rolling(20).mean().replace(0, np.nan)
        out["volume_ratio"] = out["volume"] / vol_ma

        if "bid" in out.columns and "ask" in out.columns:
            total = (out["bid"] + out["ask"]).replace(0, np.nan)
            out["bid_ask_imbalance"] = (out["bid"] - out["ask"]) / total
            out["spread_pct"] = (out["ask"] - out["bid"]) / out["close"].replace(0, np.nan) * 100.0
        else:
            out["bid_ask_imbalance"] = 0.0
            out["spread_pct"] = 0.0

        if "timestamp" in out.columns:
            ts = pd.to_datetime(out["timestamp"])
        elif isinstance(out.index, pd.DatetimeIndex):
            ts = out.index.to_series()
        else:
            ts = pd.Series(pd.NaT, index=out.index)

        out["hour"] = ts.dt.hour.fillna(0).astype(float)
        out["minute"] = ts.dt.minute.fillna(0).astype(float)
        out["day_of_week"] = ts.dt.dayofweek.fillna(0).astype(float)
        out["is_session_start"] = ((out["hour"] == 10) & (out["minute"] <= 15)).astype(float)
        out["is_session_end"] = ((out["hour"] == 18) & (out["minute"] >= 30)).astype(float)

        out["tick_direction"] = np.sign(out["close"].diff()).fillna(0)

        feature_cols = [
            c for c in out.columns
            if c not in ("open", "high", "low", "close", "volume", "bid", "ask", "timestamp")
        ]

        for lag in self._LAG_STEPS:
            for col in list(feature_cols):
                out[f"{col}_lag{lag}"] = out[col].shift(lag)

        self._feature_names = [
            c for c in out.columns
            if c not in ("open", "high", "low", "close", "volume", "bid", "ask", "timestamp")
        ]

        return out[self._feature_names].copy()

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply MinMax scaling (0-1). Fits on first call, reuses bounds after."""
        if self._min_vals is None or self._max_vals is None:
            self._min_vals = df.min()
            self._max_vals = df.max()

        range_vals = (self._max_vals - self._min_vals).replace(0, 1.0)
        return (df - self._min_vals) / range_vals

    def get_feature_names(self) -> list[str]:
        return list(self._feature_names)
