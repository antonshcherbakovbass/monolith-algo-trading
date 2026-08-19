from __future__ import annotations
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
import httpx
from loguru import logger
from .base_agent import BaseAgent, AgentSignal, AgentRole, Action
from ..core.config_loader import get_agent_params


@dataclass
class NewsItem:
    title: str
    summary: str
    source: str
    url: str
    published: datetime
    tickers: list[str]
    sentiment: float = 0.0
    urgency: float = 0.0


class NewsAgent(BaseAgent):
    """News analyst agent that monitors financial news and generates trading signals."""

    def __init__(self, config: dict, data_feed: Any = None, order_manager: Any = None, db: Any = None):
        agent_cfg = get_agent_params(config, "news")
        super().__init__("news", AgentRole.NEWS, config, data_feed, order_manager, db,
                         loop_interval=agent_cfg.get("check_interval_sec", 300.0))
        self.rss_feeds = agent_cfg.get("rss_feeds", [
            "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
            "https://www.interfax.ru/rss.asp",
        ])
        ai_cfg = config.get("ai", {})
        self.ollama_url = ai_cfg.get("base_url", "http://localhost:11434")
        self.ollama_model = ai_cfg.get("model", "llama3.1")
        self.instruments = config.get("instruments", {}).get("stocks", [])
        self.seen_urls: set[str] = set()
        self.news_history: list[NewsItem] = []
        self.ticker_keywords: dict[str, list[str]] = {
            "SBER": ["сбер", "сбербанк", "sber"],
            "GAZP": ["газпром", "gazprom", "газ"],
            "LKOH": ["лукойл", "lukoil"],
            "YNDX": ["яндекс", "yandex"],
            "ROSN": ["роснефть", "rosneft"],
            "VTBR": ["втб", "vtb"],
            "GMKN": ["норникель", "норильский никель", "norilsk"],
            "NVTK": ["новатэк", "novatek"],
            "MGNT": ["магнит", "magnit"],
            "TATN": ["татнефть", "tatneft"],
        }
        self.critical_keywords = [
            "санкции", "ключевая ставка", "цб рф", "центробанк", "дефолт",
            "дивиденды", "buyback", "обратный выкуп", "девальвация",
            "мобилизация", "нефть", "brent", "опек",
        ]

    async def analyze(self) -> list[AgentSignal]:
        signals: list[AgentSignal] = []
        news_items = await self._fetch_news()
        for item in news_items:
            if item.url in self.seen_urls:
                continue
            self.seen_urls.add(item.url)
            sentiment = await self._analyze_sentiment(item)
            item.sentiment = sentiment
            tickers = self._extract_tickers(item)
            item.tickers = tickers
            urgency = self._calc_urgency(item)
            item.urgency = urgency
            self.news_history.append(item)
            if abs(sentiment) > 0.3 and tickers:
                for ticker in tickers:
                    action = Action.BUY if sentiment > 0.3 else Action.SELL
                    signals.append(AgentSignal(
                        ticker=ticker, action=action,
                        confidence=min(abs(sentiment) * urgency, 0.9),
                        reasoning=f"News: {item.title[:100]} (sentiment={sentiment:.2f}, urgency={urgency:.1f})",
                        strategy_name="news_driven", urgency=urgency,
                    ))
        if len(self.news_history) > 500:
            self.news_history = self.news_history[-300:]
        if len(self.seen_urls) > 5000:
            self.seen_urls = set(list(self.seen_urls)[-3000:])
        return signals

    async def _fetch_news(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        try:
            import feedparser
        except ImportError:
            self.log.warning("feedparser not installed, skipping RSS")
            return items
        for feed_url in self.rss_feeds:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        continue
                feed = feedparser.parse(resp.text)
                for entry in feed.entries[:20]:
                    pub = datetime.now()
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            from time import mktime
                            pub = datetime.fromtimestamp(mktime(entry.published_parsed))
                        except Exception:
                            pass
                    if pub < datetime.now() - timedelta(hours=24):
                        continue
                    items.append(NewsItem(
                        title=getattr(entry, "title", ""),
                        summary=getattr(entry, "summary", "")[:500],
                        source=feed_url, url=getattr(entry, "link", ""),
                        published=pub, tickers=[],
                    ))
            except Exception as e:
                self.log.debug(f"RSS fetch error {feed_url}: {e}")
        return items

    async def _analyze_sentiment(self, item: NewsItem) -> float:
        prompt = (
            f"Оцени влияние этой финансовой новости на российский фондовый рынок. "
            f"Ответь ТОЛЬКО числом от -1.0 (очень негативно) до 1.0 (очень позитивно). "
            f"Заголовок: {item.title}\n"
            f"Текст: {item.summary[:300]}"
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": self.ollama_model, "prompt": prompt, "stream": False},
                )
                if resp.status_code == 200:
                    text = resp.json().get("response", "0").strip()
                    for token in text.replace(",", ".").split():
                        try:
                            val = float(token)
                            return max(-1.0, min(1.0, val))
                        except ValueError:
                            continue
        except Exception as e:
            self.log.debug(f"Sentiment LLM error: {e}")
        return 0.0

    def _extract_tickers(self, item: NewsItem) -> list[str]:
        text = (item.title + " " + item.summary).lower()
        found = []
        for ticker, keywords in self.ticker_keywords.items():
            if any(kw in text for kw in keywords):
                found.append(ticker)
        return found

    def _calc_urgency(self, item: NewsItem) -> float:
        text = (item.title + " " + item.summary).lower()
        urgency = 0.5
        for kw in self.critical_keywords:
            if kw in text:
                urgency = min(urgency + 0.2, 1.0)
        age_hours = (datetime.now() - item.published).total_seconds() / 3600
        if age_hours < 1:
            urgency *= 1.3
        elif age_hours > 6:
            urgency *= 0.5
        return min(urgency, 1.0)

    async def get_market_sentiment(self) -> float:
        recent = [n.sentiment for n in self.news_history[-20:] if n.sentiment != 0]
        if not recent:
            return 0.0
        return sum(recent) / len(recent)

    async def get_status(self) -> dict:
        return {
            "name": self.name, "running": self._running,
            "news_processed": len(self.seen_urls),
            "market_sentiment": await self.get_market_sentiment(),
            "recent_news": len(self.news_history),
        }
