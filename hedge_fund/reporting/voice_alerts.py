"""
Voice Alert System — speaks critical trading events aloud.

Uses Windows SAPI (pyttsx3) or edge-tts for text-to-speech
to announce critical events like large P&L, risk alerts, and trade fills.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from datetime import datetime
from typing import Any
from loguru import logger


class VoiceAlertSystem:
    """
    Announces critical trading events via text-to-speech.
    
    Alert levels:
    - INFO: trade fills, position changes
    - WARNING: approaching risk limits, high drawdown
    - CRITICAL: emergency stop, QUIK disconnection, max loss
    
    Uses pyttsx3 (offline, Windows SAPI) with fallback to edge-tts.
    Runs TTS in a separate thread to avoid blocking the event loop.
    """

    def __init__(self, enabled: bool = True, volume: float = 0.8, rate: int = 180):
        self.enabled = enabled
        self.volume = volume
        self.rate = rate
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=50)
        self._thread: threading.Thread | None = None
        self._running = False
        self._engine: Any = None
        self._engine_available = False
        self.log = logger.bind(component="voice_alerts")

    def start(self) -> None:
        if not self.enabled:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        self.log.info("Voice alert system started")

    def stop(self) -> None:
        self._running = False
        self._queue.put(("__STOP__", ""))
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self.log.info("Voice alert system stopped")

    def _worker(self) -> None:
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)
            voices = self._engine.getProperty("voices")
            # Try to find Russian voice
            for voice in voices:
                if "russian" in voice.name.lower() or "ru" in voice.id.lower():
                    self._engine.setProperty("voice", voice.id)
                    break
            self._engine_available = True
            self.log.info("TTS engine initialized (pyttsx3)")
        except Exception as e:
            self.log.warning(f"pyttsx3 not available: {e}. Voice alerts will be logged only.")
            self._engine_available = False

        while self._running:
            try:
                level, text = self._queue.get(timeout=2)
                if level == "__STOP__":
                    break
                self._speak(text, level)
            except queue.Empty:
                continue
            except Exception as e:
                self.log.error(f"Voice worker error: {e}")

    def _speak(self, text: str, level: str) -> None:
        self.log.info(f"Voice [{level}]: {text}")
        if self._engine_available and self._engine:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                self.log.debug(f"TTS error: {e}")

    def alert(self, text: str, level: str = "INFO") -> None:
        if not self.enabled:
            return
        try:
            self._queue.put_nowait((level, text))
        except queue.Full:
            self.log.warning("Voice queue full, dropping alert")

    # Convenience methods for common events
    def trade_filled(self, ticker: str, side: str, qty: int, price: float) -> None:
        self.alert(f"Сделка: {side} {qty} {ticker} по {price:.2f}", "INFO")

    def pnl_update(self, daily_pnl: float) -> None:
        if abs(daily_pnl) > 10000:
            level = "WARNING" if daily_pnl < 0 else "INFO"
            sign = "плюс" if daily_pnl > 0 else "минус"
            self.alert(f"Дневной результат: {sign} {abs(daily_pnl):,.0f} рублей", level)

    def risk_warning(self, message: str) -> None:
        self.alert(f"Внимание! Риск: {message}", "WARNING")

    def critical_alert(self, message: str) -> None:
        self.alert(f"КРИТИЧЕСКАЯ СИТУАЦИЯ! {message}", "CRITICAL")

    def system_status(self, status: str) -> None:
        self.alert(f"Система: {status}", "INFO")

    def market_open(self) -> None:
        self.alert("Московская биржа открыта. Торговля начинается.", "INFO")

    def market_close(self) -> None:
        self.alert("Основная сессия Московской биржи завершена.", "INFO")

    def emergency_stop(self) -> None:
        self.alert("АВАРИЙНАЯ ОСТАНОВКА! Все позиции закрываются!", "CRITICAL")
