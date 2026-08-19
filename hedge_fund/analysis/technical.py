from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class SignalDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class Signal:
    indicator: str
    direction: SignalDirection
    strength: float  # 0.0 - 1.0


@dataclass
class FibonacciLevels:
    level_0: float
    level_236: float
    level_382: float
    level_500: float
    level_618: float
    level_786: float
    level_1: float


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(
    series: pd.Series, period: int = 20, std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    middle = series.rolling(window=period).mean()
    rolling_std = series.rolling(window=period).std()
    upper = middle + std * rolling_std
    lower = middle - std * rolling_std
    return upper, middle, lower


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3
) -> tuple[pd.Series, pd.Series]:
    low_min = df["low"].rolling(window=k_period).min()
    high_max = df["high"].rolling(window=k_period).max()
    k = 100.0 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    d = k.rolling(window=d_period).mean()
    return k, d


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff())
    direction.iloc[0] = 0
    return (direction * df["volume"]).cumsum()


def volume_profile(df: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
    price_min = df["low"].min()
    price_max = df["high"].max()
    edges = np.linspace(price_min, price_max, bins + 1)
    mid_points = (edges[:-1] + edges[1:]) / 2.0
    volumes = np.zeros(bins)
    for _, row in df.iterrows():
        for i in range(bins):
            if row["low"] <= edges[i + 1] and row["high"] >= edges[i]:
                volumes[i] += row["volume"] / max(
                    1, sum(
                        1 for j in range(bins)
                        if row["low"] <= edges[j + 1] and row["high"] >= edges[j]
                    )
                )
    return pd.DataFrame({"price": mid_points, "volume": volumes})


def vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    return cum_tp_vol / cum_vol.replace(0, np.nan)


def ichimoku(
    df: pd.DataFrame,
    tenkan: int = 9,
    kijun: int = 26,
    senkou_b: int = 52,
) -> dict[str, pd.Series]:
    high = df["high"]
    low = df["low"]
    tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2.0
    kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2.0
    senkou_a = ((tenkan_sen + kijun_sen) / 2.0).shift(kijun)
    senkou_b_line = (
        (high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2.0
    ).shift(kijun)
    chikou = df["close"].shift(-kijun)
    return {
        "tenkan_sen": tenkan_sen,
        "kijun_sen": kijun_sen,
        "senkou_a": senkou_a,
        "senkou_b": senkou_b_line,
        "chikou": chikou,
    }


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)

    atr_val = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(span=period, adjust=False).mean() / atr_val.replace(0, np.nan)
    minus_di = 100.0 * minus_dm.ewm(span=period, adjust=False).mean() / atr_val.replace(0, np.nan)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(span=period, adjust=False).mean()


def fibonacci_retracement(high: float, low: float) -> FibonacciLevels:
    diff = high - low
    return FibonacciLevels(
        level_0=high,
        level_236=high - 0.236 * diff,
        level_382=high - 0.382 * diff,
        level_500=high - 0.500 * diff,
        level_618=high - 0.618 * diff,
        level_786=high - 0.786 * diff,
        level_1=low,
    )


def support_resistance(df: pd.DataFrame, window: int = 5) -> dict[str, list[float]]:
    highs = df["high"]
    lows = df["low"]
    pivot_highs: list[float] = []
    pivot_lows: list[float] = []
    for i in range(window, len(df) - window):
        if highs.iloc[i] == highs.iloc[i - window : i + window + 1].max():
            pivot_highs.append(float(highs.iloc[i]))
        if lows.iloc[i] == lows.iloc[i - window : i + window + 1].min():
            pivot_lows.append(float(lows.iloc[i]))
    return {"resistance": sorted(set(pivot_highs), reverse=True), "support": sorted(set(pivot_lows))}


def detect_doji(df: pd.DataFrame, threshold: float = 0.05) -> pd.Series:
    body = (df["close"] - df["open"]).abs()
    full_range = df["high"] - df["low"]
    return body <= threshold * full_range.replace(0, np.nan)


def detect_hammer(df: pd.DataFrame, body_ratio: float = 0.3, shadow_ratio: float = 2.0) -> pd.Series:
    body = (df["close"] - df["open"]).abs()
    full_range = (df["high"] - df["low"]).replace(0, np.nan)
    lower_shadow = pd.concat([df["open"], df["close"]], axis=1).min(axis=1) - df["low"]
    upper_shadow = df["high"] - pd.concat([df["open"], df["close"]], axis=1).max(axis=1)
    return (
        (body / full_range <= body_ratio)
        & (lower_shadow >= shadow_ratio * body)
        & (upper_shadow <= body)
    )


def detect_engulfing(df: pd.DataFrame) -> pd.Series:
    prev_open = df["open"].shift(1)
    prev_close = df["close"].shift(1)
    bullish = (prev_close < prev_open) & (df["close"] > df["open"]) & (df["open"] <= prev_close) & (df["close"] >= prev_open)
    bearish = (prev_close > prev_open) & (df["close"] < df["open"]) & (df["open"] >= prev_close) & (df["close"] <= prev_open)
    result = pd.Series(0, index=df.index)
    result[bullish] = 1
    result[bearish] = -1
    return result


def detect_morning_star(df: pd.DataFrame) -> pd.Series:
    c1_bear = df["close"].shift(2) < df["open"].shift(2)
    c2_small = (df["close"].shift(1) - df["open"].shift(1)).abs() < (df["open"].shift(2) - df["close"].shift(2)).abs() * 0.3
    c3_bull = df["close"] > df["open"]
    c3_above_mid = df["close"] > (df["open"].shift(2) + df["close"].shift(2)) / 2.0
    return c1_bear & c2_small & c3_bull & c3_above_mid


def detect_evening_star(df: pd.DataFrame) -> pd.Series:
    c1_bull = df["close"].shift(2) > df["open"].shift(2)
    c2_small = (df["close"].shift(1) - df["open"].shift(1)).abs() < (df["close"].shift(2) - df["open"].shift(2)).abs() * 0.3
    c3_bear = df["close"] < df["open"]
    c3_below_mid = df["close"] < (df["open"].shift(2) + df["close"].shift(2)) / 2.0
    return c1_bull & c2_small & c3_bear & c3_below_mid


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["rsi"] = rsi(out["close"])
    out["macd"], out["macd_signal"], out["macd_hist"] = macd(out["close"])
    out["bb_upper"], out["bb_middle"], out["bb_lower"] = bollinger_bands(out["close"])
    out["ema_9"] = ema(out["close"], 9)
    out["ema_21"] = ema(out["close"], 21)
    out["sma_50"] = sma(out["close"], 50)
    out["sma_200"] = sma(out["close"], 200)
    out["atr"] = atr(out)
    out["stoch_k"], out["stoch_d"] = stochastic(out)
    out["obv"] = obv(out)
    out["vwap"] = vwap(out)
    ichi = ichimoku(out)
    for k, v in ichi.items():
        out[f"ichi_{k}"] = v
    out["adx"] = adx(out)
    out["doji"] = detect_doji(out)
    out["hammer"] = detect_hammer(out)
    out["engulfing"] = detect_engulfing(out)
    out["morning_star"] = detect_morning_star(out)
    out["evening_star"] = detect_evening_star(out)
    return out


def get_signals(df: pd.DataFrame) -> list[Signal]:
    signals: list[Signal] = []
    if len(df) < 2:
        return signals
    last = df.iloc[-1]
    prev = df.iloc[-2]

    rsi_val = last.get("rsi")
    if rsi_val is not None and not np.isnan(rsi_val):
        if rsi_val < 30:
            signals.append(Signal("RSI", SignalDirection.BULLISH, min(1.0, (30 - rsi_val) / 30)))
        elif rsi_val > 70:
            signals.append(Signal("RSI", SignalDirection.BEARISH, min(1.0, (rsi_val - 70) / 30)))

    macd_val = last.get("macd")
    macd_sig = last.get("macd_signal")
    prev_macd = prev.get("macd")
    prev_sig = prev.get("macd_signal")
    if all(v is not None and not np.isnan(v) for v in [macd_val, macd_sig, prev_macd, prev_sig]):
        if prev_macd <= prev_sig and macd_val > macd_sig:
            signals.append(Signal("MACD", SignalDirection.BULLISH, 0.7))
        elif prev_macd >= prev_sig and macd_val < macd_sig:
            signals.append(Signal("MACD", SignalDirection.BEARISH, 0.7))

    close = last.get("close")
    bb_lower = last.get("bb_lower")
    bb_upper = last.get("bb_upper")
    if all(v is not None and not np.isnan(v) for v in [close, bb_lower, bb_upper]):
        if close < bb_lower:
            signals.append(Signal("Bollinger", SignalDirection.BULLISH, 0.6))
        elif close > bb_upper:
            signals.append(Signal("Bollinger", SignalDirection.BEARISH, 0.6))

    stoch_k = last.get("stoch_k")
    stoch_d = last.get("stoch_d")
    if stoch_k is not None and stoch_d is not None and not np.isnan(stoch_k) and not np.isnan(stoch_d):
        if stoch_k < 20 and stoch_d < 20:
            signals.append(Signal("Stochastic", SignalDirection.BULLISH, 0.6))
        elif stoch_k > 80 and stoch_d > 80:
            signals.append(Signal("Stochastic", SignalDirection.BEARISH, 0.6))

    adx_val = last.get("adx")
    if adx_val is not None and not np.isnan(adx_val):
        if adx_val > 25:
            ema9 = last.get("ema_9")
            ema21 = last.get("ema_21")
            if ema9 is not None and ema21 is not None and not np.isnan(ema9) and not np.isnan(ema21):
                direction = SignalDirection.BULLISH if ema9 > ema21 else SignalDirection.BEARISH
                signals.append(Signal("ADX", direction, min(1.0, adx_val / 50)))

    if last.get("doji", False):
        signals.append(Signal("Doji", SignalDirection.NEUTRAL, 0.4))
    if last.get("hammer", False):
        signals.append(Signal("Hammer", SignalDirection.BULLISH, 0.5))
    eng = last.get("engulfing", 0)
    if eng == 1:
        signals.append(Signal("Engulfing", SignalDirection.BULLISH, 0.7))
    elif eng == -1:
        signals.append(Signal("Engulfing", SignalDirection.BEARISH, 0.7))
    if last.get("morning_star", False):
        signals.append(Signal("MorningStar", SignalDirection.BULLISH, 0.8))
    if last.get("evening_star", False):
        signals.append(Signal("EveningStar", SignalDirection.BEARISH, 0.8))

    return signals
