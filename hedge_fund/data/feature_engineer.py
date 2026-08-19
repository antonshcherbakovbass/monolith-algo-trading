"""Feature engineering for ML training on MOEX OHLCV data."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils.logger import get_logger

log = get_logger("data.feature_engineer")


class FeatureEngineer:
    """Creates ML features from OHLCV data."""

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicator features for ML training.

        Expects columns: datetime, open, high, low, close, volume.
        """
        out = df.copy()
        c = out["close"]

        # Returns & log returns
        for w in (1, 5, 10, 20):
            out[f"return_{w}d"] = c.pct_change(w)
            out[f"log_return_{w}d"] = np.log(c / c.shift(w))

        # RSI-14
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        out["rsi_14"] = 100.0 - 100.0 / (1.0 + rs)

        # MACD (12, 26, 9)
        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal = macd_line.ewm(span=9, adjust=False).mean()
        out["macd"] = macd_line
        out["macd_signal"] = signal
        out["macd_hist"] = macd_line - signal

        # Bollinger Band width
        sma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        out["bb_upper"] = sma20 + 2 * std20
        out["bb_lower"] = sma20 - 2 * std20
        bb_range = (out["bb_upper"] - out["bb_lower"]).replace(0, np.nan)
        out["bb_width"] = bb_range / sma20
        out["bb_position"] = (c - out["bb_lower"]) / bb_range

        # ATR-14
        tr = pd.concat(
            [
                out["high"] - out["low"],
                (out["high"] - c.shift(1)).abs(),
                (out["low"] - c.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        out["atr_14"] = tr.rolling(14).mean()

        # Volume ratio vs 20-day avg
        vol_ma = out["volume"].rolling(20).mean().replace(0, np.nan)
        out["volume_ratio"] = out["volume"] / vol_ma

        # Price vs SMA
        for period in (20, 50, 200):
            sma = c.rolling(period).mean()
            out[f"price_vs_sma{period}"] = (c - sma) / sma.replace(0, np.nan)

        # Volatility (20-day rolling std of returns)
        out["volatility_20d"] = c.pct_change().rolling(20).std()

        # Time features
        if "datetime" in out.columns:
            dt = pd.to_datetime(out["datetime"])
            out["day_of_week"] = dt.dt.dayofweek.astype(float)
            out["hour_of_day"] = dt.dt.hour.astype(float)

        # Momentum (ROC)
        for w in (10, 20):
            shifted = c.shift(w).replace(0, np.nan)
            out[f"roc_{w}"] = (c - c.shift(w)) / shifted

        # OBV slope
        obv = (np.sign(c.diff()).fillna(0) * out["volume"]).cumsum()
        out["obv_slope"] = obv.diff(10) / 10.0

        # Stochastic oscillator (14, 3)
        low14 = out["low"].rolling(14).min()
        high14 = out["high"].rolling(14).max()
        denom = (high14 - low14).replace(0, np.nan)
        out["stoch_k"] = 100.0 * (c - low14) / denom
        out["stoch_d"] = out["stoch_k"].rolling(3).mean()

        return out

    def create_labels(
        self,
        df: pd.DataFrame,
        horizon: int = 5,
        threshold: float = 0.5,
    ) -> pd.Series:
        """Create classification labels.

        1 = up > threshold%, -1 = down > threshold%, 0 = flat.
        """
        fwd = df["close"].pct_change(horizon).shift(-horizon) * 100.0
        labels = pd.Series(0, index=df.index, dtype=int)
        labels[fwd > threshold] = 1
        labels[fwd < -threshold] = -1
        return labels

    def prepare_dataset(
        self,
        df: pd.DataFrame,
        horizon: int = 5,
        threshold: float = 0.5,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Full pipeline: features + labels, drop NaN rows."""
        featured = self.create_features(df)
        labels = self.create_labels(df, horizon=horizon, threshold=threshold)

        non_feature_cols = {
            "datetime", "open", "high", "low", "close", "volume", "value",
        }
        feature_cols = [c for c in featured.columns if c not in non_feature_cols]
        X = featured[feature_cols]

        valid = X.notna().all(axis=1) & labels.notna()
        X = X.loc[valid].reset_index(drop=True)
        y = labels.loc[valid].reset_index(drop=True)
        log.info("Dataset ready: {} samples, {} features", len(X), len(feature_cols))
        return X, y
