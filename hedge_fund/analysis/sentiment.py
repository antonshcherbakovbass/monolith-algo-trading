from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp


@dataclass
class SentimentResult:
    score: float  # -1.0 (bearish) to 1.0 (bullish)
    confidence: float  # 0.0 to 1.0
    key_entities: list[str] = field(default_factory=list)
    market_impact: str = ""


class SentimentAnalyzer:
    SYSTEM_PROMPT = (
        "Ты — финансовый аналитик, специализирующийся на российском фондовом рынке (MOEX). "
        "Анализируй текст новости и определи:\n"
        "1. sentiment_score: число от -1.0 (крайне негативно для рынка) до 1.0 (крайне позитивно)\n"
        "2. confidence: уверенность в оценке от 0.0 до 1.0\n"
        "3. key_entities: список упомянутых тикеров, компаний, секторов\n"
        "4. market_impact: краткое описание влияния на рынок\n\n"
        "Учитывай специфику: санкции, решения ЦБ РФ по ставке, курс рубля, "
        "геополитику, дивидендные отсечки, buyback программы.\n\n"
        "Ответь СТРОГО в формате JSON:\n"
        '{"sentiment_score": <float>, "confidence": <float>, '
        '"key_entities": [<str>, ...], "market_impact": "<str>"}'
    )

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "llama3",
        cache_ttl: int = 1800,
    ) -> None:
        self._ollama_url = ollama_url.rstrip("/")
        self._model = model
        self._cache: dict[str, tuple[SentimentResult, float]] = {}
        self._cache_ttl = cache_ttl

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _get_cached(self, text: str) -> Optional[SentimentResult]:
        key = self._cache_key(text)
        if key in self._cache:
            result, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return result
            del self._cache[key]
        return None

    def _set_cache(self, text: str, result: SentimentResult) -> None:
        self._cache[self._cache_key(text)] = (result, time.time())

    async def _call_ollama(self, prompt: str) -> str:
        url = f"{self._ollama_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": self.SYSTEM_PROMPT,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("response", "")

    def _parse_response(self, raw: str) -> SentimentResult:
        import json

        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return SentimentResult(score=0.0, confidence=0.0, market_impact="parse_error")
        try:
            data = json.loads(raw[start:end])
        except json.JSONDecodeError:
            return SentimentResult(score=0.0, confidence=0.0, market_impact="parse_error")

        return SentimentResult(
            score=max(-1.0, min(1.0, float(data.get("sentiment_score", 0)))),
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0)))),
            key_entities=data.get("key_entities", []),
            market_impact=str(data.get("market_impact", "")),
        )

    async def analyze_text(self, text: str) -> SentimentResult:
        cached = self._get_cached(text)
        if cached is not None:
            return cached

        prompt = f"Проанализируй следующую финансовую новость:\n\n{text}"
        raw = await self._call_ollama(prompt)
        result = self._parse_response(raw)
        self._set_cache(text, result)
        return result

    async def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        results: list[SentimentResult] = []
        for text in texts:
            result = await self.analyze_text(text)
            results.append(result)
        return results
