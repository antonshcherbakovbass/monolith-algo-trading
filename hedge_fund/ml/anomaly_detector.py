"""
ML Anomaly Detector for market manipulation and structural anomalies.

Detects spoofing, wash trading, unusual volume patterns, and price
dislocations that may indicate manipulation or exploitable inefficiencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class Anomaly:
    timestamp: datetime
    ticker: str
    anomaly_type: str  # "spoofing", "wash_trade", "volume_spike", "price_dislocation", "flash_crash", "layering"
    severity: float  # 0-1
    description: str
    raw_data: dict[str, Any] = field(default_factory=dict)
    actionable: bool = False
    suggested_action: str = ""  # "avoid", "exploit_long", "exploit_short"


class AnomalyDetector:
    """
    Detects market anomalies using statistical and ML methods.
    
    Detection types:
    - Volume anomalies (unusual spikes vs historical pattern)
    - Price dislocations (deviation from fair value models)
    - Order book spoofing (large orders that disappear)
    - Wash trading (circular volume patterns)
    - Flash crashes / spikes
    - Correlation breaks (sudden decorrelation of normally-correlated pairs)
    """

    def __init__(self, lookback: int = 100):
        self.lookback = lookback
        self.history: dict[str, list[Anomaly]] = {}
        self.log = logger.bind(component="anomaly_detector")

    def detect_all(self, ticker: str, prices: np.ndarray, volumes: np.ndarray,
                   orderbook_snapshots: list[dict] | None = None) -> list[Anomaly]:
        anomalies: list[Anomaly] = []

        if len(prices) < 20:
            return anomalies

        anomalies.extend(self._detect_volume_anomaly(ticker, prices, volumes))
        anomalies.extend(self._detect_price_dislocation(ticker, prices))
        anomalies.extend(self._detect_flash_event(ticker, prices, volumes))

        if orderbook_snapshots and len(orderbook_snapshots) >= 5:
            anomalies.extend(self._detect_spoofing(ticker, orderbook_snapshots))

        self.history.setdefault(ticker, []).extend(anomalies)
        if len(self.history[ticker]) > 500:
            self.history[ticker] = self.history[ticker][-300:]

        return anomalies

    def _detect_volume_anomaly(self, ticker: str, prices: np.ndarray, volumes: np.ndarray) -> list[Anomaly]:
        anomalies = []
        if len(volumes) < 30:
            return anomalies

        vol_mean = np.mean(volumes[-30:])
        vol_std = np.std(volumes[-30:])
        if vol_std < 1:
            return anomalies

        z = (volumes[-1] - vol_mean) / vol_std
        ret = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] > 0 else 0
        ret_std = np.std(np.diff(prices[-30:]) / prices[-31:-1])

        # Huge volume, tiny price move = accumulation/distribution
        if z > 3.0 and abs(ret) < ret_std * 0.5:
            severity = min(z / 5.0, 1.0)
            anomalies.append(Anomaly(
                timestamp=datetime.now(), ticker=ticker,
                anomaly_type="volume_spike",
                severity=severity,
                description=f"Volume z-score={z:.1f} with negligible price move ({ret*100:.3f}%)",
                raw_data={"volume_zscore": z, "return": ret},
                actionable=True,
                suggested_action="exploit_long" if ret > 0 else "exploit_short",
            ))

        # Volume dry-up before big move (compression)
        if z < -1.5 and len(volumes) >= 50:
            recent_vol_trend = np.mean(volumes[-5:]) / max(np.mean(volumes[-50:-5]), 1)
            if recent_vol_trend < 0.4:
                anomalies.append(Anomaly(
                    timestamp=datetime.now(), ticker=ticker,
                    anomaly_type="volume_spike",
                    severity=0.5,
                    description=f"Volume compression: recent={recent_vol_trend:.2f}x average (breakout imminent?)",
                    raw_data={"vol_ratio": recent_vol_trend},
                    actionable=False,
                ))

        return anomalies

    def _detect_price_dislocation(self, ticker: str, prices: np.ndarray) -> list[Anomaly]:
        anomalies = []
        if len(prices) < 50:
            return anomalies

        # Check deviation from multiple moving averages
        sma20 = np.mean(prices[-20:])
        sma50 = np.mean(prices[-50:])
        std20 = np.std(prices[-20:])

        dev_from_sma20 = (prices[-1] - sma20) / max(std20, 1e-10)

        if abs(dev_from_sma20) > 3.0:
            direction = "above" if dev_from_sma20 > 0 else "below"
            anomalies.append(Anomaly(
                timestamp=datetime.now(), ticker=ticker,
                anomaly_type="price_dislocation",
                severity=min(abs(dev_from_sma20) / 5.0, 1.0),
                description=f"Price {abs(dev_from_sma20):.1f} std {direction} SMA20",
                raw_data={"z_score": dev_from_sma20, "sma20": sma20, "price": prices[-1]},
                actionable=True,
                suggested_action="exploit_short" if dev_from_sma20 > 3 else "exploit_long",
            ))

        # Gap detection
        returns = np.diff(prices) / prices[:-1]
        last_return = returns[-1]
        ret_std = np.std(returns[-50:])
        if abs(last_return) > ret_std * 4:
            anomalies.append(Anomaly(
                timestamp=datetime.now(), ticker=ticker,
                anomaly_type="price_dislocation",
                severity=min(abs(last_return / ret_std) / 6.0, 1.0),
                description=f"Price gap: {last_return*100:.2f}% ({abs(last_return/ret_std):.1f} sigma)",
                raw_data={"return": last_return, "sigma": abs(last_return / ret_std)},
                actionable=abs(last_return / ret_std) > 5,
                suggested_action="exploit_short" if last_return > 0 else "exploit_long",
            ))

        return anomalies

    def _detect_flash_event(self, ticker: str, prices: np.ndarray, volumes: np.ndarray) -> list[Anomaly]:
        anomalies = []
        if len(prices) < 10:
            return anomalies

        # Flash crash: rapid drop followed by recovery
        recent = prices[-10:]
        min_idx = np.argmin(recent)
        max_idx = np.argmax(recent)

        if min_idx > 0 and min_idx < len(recent) - 1:
            drop = (recent[0] - recent[min_idx]) / recent[0]
            recovery = (recent[-1] - recent[min_idx]) / recent[min_idx] if recent[min_idx] > 0 else 0
            if drop > 0.02 and recovery > drop * 0.5:
                anomalies.append(Anomaly(
                    timestamp=datetime.now(), ticker=ticker,
                    anomaly_type="flash_crash",
                    severity=min(drop * 20, 1.0),
                    description=f"Flash crash: -{drop*100:.2f}% drop, {recovery*100:.2f}% recovery",
                    raw_data={"drop_pct": drop * 100, "recovery_pct": recovery * 100},
                    actionable=True,
                    suggested_action="exploit_long",
                ))

        return anomalies

    def _detect_spoofing(self, ticker: str, snapshots: list[dict]) -> list[Anomaly]:
        anomalies = []
        if len(snapshots) < 5:
            return anomalies

        # Track large orders that appear and disappear
        for i in range(1, len(snapshots)):
            prev_bids = {level.get("price", 0): level.get("qty", 0) for level in snapshots[i-1].get("bids", [])}
            curr_bids = {level.get("price", 0): level.get("qty", 0) for level in snapshots[i].get("bids", [])}

            for price, qty in prev_bids.items():
                avg_size = np.mean([l.get("qty", 0) for l in snapshots[i-1].get("bids", [])[:5]]) if snapshots[i-1].get("bids") else 1
                if qty > avg_size * 5 and price not in curr_bids:
                    anomalies.append(Anomaly(
                        timestamp=datetime.now(), ticker=ticker,
                        anomaly_type="spoofing",
                        severity=0.7,
                        description=f"Potential spoofing: large bid ({qty}) at {price} disappeared",
                        raw_data={"price": price, "vanished_qty": qty},
                        actionable=False,
                        suggested_action="avoid",
                    ))
                    break

        return anomalies

    def detect_correlation_break(
        self, returns_a: np.ndarray, returns_b: np.ndarray,
        ticker_a: str, ticker_b: str,
        window: int = 30, threshold: float = 0.3,
    ) -> Anomaly | None:
        if len(returns_a) < window * 2 or len(returns_b) < window * 2:
            return None

        hist_corr = np.corrcoef(returns_a[-window*2:-window], returns_b[-window*2:-window])[0, 1]
        recent_corr = np.corrcoef(returns_a[-window:], returns_b[-window:])[0, 1]

        if abs(hist_corr - recent_corr) > threshold and abs(hist_corr) > 0.5:
            return Anomaly(
                timestamp=datetime.now(),
                ticker=f"{ticker_a}/{ticker_b}",
                anomaly_type="correlation_break",
                severity=min(abs(hist_corr - recent_corr), 1.0),
                description=f"Correlation break: {hist_corr:.2f} -> {recent_corr:.2f}",
                raw_data={"historical_corr": hist_corr, "recent_corr": recent_corr},
                actionable=True,
                suggested_action="exploit_long" if recent_corr < hist_corr else "exploit_short",
            )
        return None
