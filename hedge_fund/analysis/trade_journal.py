"""
AI Trade Journal — learns from every trade.

Analyzes past trades using LLM to identify patterns, mistakes,
and improvement opportunities. Generates actionable feedback
for each agent.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import numpy as np
import httpx
from loguru import logger


@dataclass
class TradeReview:
    trade_id: int
    ticker: str
    side: str
    entry_price: float
    exit_price: float
    pnl: float
    agent: str
    strategy: str
    entry_reasoning: str = ""
    review_text: str = ""
    grade: str = ""  # A, B, C, D, F
    mistakes: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)
    reviewed_at: datetime = field(default_factory=datetime.now)


@dataclass
class AgentPerformanceReport:
    agent_name: str
    period_days: int
    total_trades: int
    win_rate: float
    avg_pnl: float
    sharpe: float
    best_trade: dict | None = None
    worst_trade: dict | None = None
    common_mistakes: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class TradeJournal:
    """
    AI-powered trade journal and performance analyzer.
    
    Features:
    - Reviews every closed trade with LLM analysis
    - Identifies recurring mistakes per agent
    - Tracks improvement over time
    - Generates weekly performance reports
    - Provides actionable feedback for strategy adjustments
    - Pattern recognition: what market conditions produce best results
    """

    def __init__(self, config: dict):
        ai_cfg = config.get("ai", {})
        self.ollama_url = ai_cfg.get("base_url", "http://localhost:11434")
        self.ollama_model = ai_cfg.get("model", "llama3.1")
        self.reviews: list[TradeReview] = []
        self.agent_stats: dict[str, list[dict]] = {}
        self.log = logger.bind(component="trade_journal")

    async def review_trade(
        self,
        trade_id: int,
        ticker: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        agent: str,
        strategy: str,
        entry_reasoning: str = "",
        market_context: str = "",
    ) -> TradeReview:
        review = TradeReview(
            trade_id=trade_id, ticker=ticker, side=side,
            entry_price=entry_price, exit_price=exit_price,
            pnl=pnl, agent=agent, strategy=strategy,
            entry_reasoning=entry_reasoning,
        )

        # Quick statistical grading (no LLM needed)
        ret_pct = (exit_price - entry_price) / entry_price * 100 if side == "BUY" else (entry_price - exit_price) / entry_price * 100
        review.grade = self._grade_trade(ret_pct, pnl)

        # Identify obvious mistakes
        if pnl < 0:
            if abs(ret_pct) > 3:
                review.mistakes.append("Large loss without stop-loss activation")
            if "momentum" in strategy.lower() and ret_pct < -1:
                review.mistakes.append("Chased momentum that reversed")
        if abs(ret_pct) < 0.1 and pnl < 0:
            review.mistakes.append("Commission-eaten trade (too tight target)")

        # LLM deep analysis for significant trades
        if abs(pnl) > 1000 or abs(ret_pct) > 2:
            llm_analysis = await self._llm_review(review, market_context)
            if llm_analysis:
                review.review_text = llm_analysis.get("review", "")
                review.lessons.extend(llm_analysis.get("lessons", []))
                review.improvement_suggestions.extend(llm_analysis.get("suggestions", []))

        # Track per-agent stats
        self.agent_stats.setdefault(agent, []).append({
            "pnl": pnl, "return_pct": ret_pct, "grade": review.grade,
            "strategy": strategy, "ticker": ticker, "timestamp": datetime.now().isoformat(),
        })

        self.reviews.append(review)
        if len(self.reviews) > 2000:
            self.reviews = self.reviews[-1000:]

        self.log.info(f"Trade #{trade_id} reviewed: {ticker} {side} grade={review.grade} pnl={pnl:+.2f}")
        return review

    def _grade_trade(self, return_pct: float, pnl: float) -> str:
        if return_pct > 2.0:
            return "A"
        elif return_pct > 0.5:
            return "B"
        elif return_pct > 0:
            return "C"
        elif return_pct > -1.0:
            return "D"
        else:
            return "F"

    async def _llm_review(self, review: TradeReview, market_context: str) -> dict | None:
        prompt = (
            f"Проанализируй эту сделку на Московской бирже как опытный трейдер:\n"
            f"Тикер: {review.ticker}, Направление: {review.side}\n"
            f"Вход: {review.entry_price}, Выход: {review.exit_price}\n"
            f"P&L: {review.pnl:+.2f} руб, Агент: {review.agent}, Стратегия: {review.strategy}\n"
            f"Причина входа: {review.entry_reasoning}\n"
            f"Рыночный контекст: {market_context}\n\n"
            f"Ответь в формате:\n"
            f"ОБЗОР: (1-2 предложения)\n"
            f"УРОКИ: (список через ;)\n"
            f"РЕКОМЕНДАЦИИ: (список через ;)"
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": self.ollama_model, "prompt": prompt, "stream": False},
                )
                if resp.status_code == 200:
                    text = resp.json().get("response", "")
                    return self._parse_llm_response(text)
        except Exception as e:
            self.log.debug(f"LLM review failed: {e}")
        return None

    def _parse_llm_response(self, text: str) -> dict:
        result: dict[str, Any] = {"review": "", "lessons": [], "suggestions": []}
        current = "review"
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            if "обзор" in lower or "review" in lower:
                current = "review"
                line = line.split(":", 1)[-1].strip()
            elif "урок" in lower or "lesson" in lower:
                current = "lessons"
                line = line.split(":", 1)[-1].strip()
            elif "рекомендац" in lower or "suggestion" in lower:
                current = "suggestions"
                line = line.split(":", 1)[-1].strip()

            if not line:
                continue
            if current == "review":
                result["review"] += line + " "
            else:
                for part in line.split(";"):
                    part = part.strip(" -•")
                    if part:
                        result[current].append(part)

        result["review"] = result["review"].strip()
        return result

    def get_agent_report(self, agent_name: str, days: int = 7) -> AgentPerformanceReport:
        stats = self.agent_stats.get(agent_name, [])
        if not stats:
            return AgentPerformanceReport(agent_name=agent_name, period_days=days,
                                          total_trades=0, win_rate=0, avg_pnl=0, sharpe=0)

        pnls = [s["pnl"] for s in stats]
        wins = [p for p in pnls if p > 0]
        returns = [s["return_pct"] for s in stats]

        avg_ret = np.mean(returns)
        std_ret = np.std(returns) if len(returns) > 1 else 1
        sharpe = avg_ret / max(std_ret, 1e-10) * np.sqrt(252)

        # Common mistakes from reviews
        agent_reviews = [r for r in self.reviews if r.agent == agent_name]
        all_mistakes: dict[str, int] = {}
        for r in agent_reviews:
            for m in r.mistakes:
                all_mistakes[m] = all_mistakes.get(m, 0) + 1
        common_mistakes = [m for m, c in sorted(all_mistakes.items(), key=lambda x: x[1], reverse=True)[:5]]

        best = max(stats, key=lambda s: s["pnl"]) if stats else None
        worst = min(stats, key=lambda s: s["pnl"]) if stats else None

        return AgentPerformanceReport(
            agent_name=agent_name,
            period_days=days,
            total_trades=len(pnls),
            win_rate=len(wins) / max(len(pnls), 1) * 100,
            avg_pnl=np.mean(pnls),
            sharpe=sharpe,
            best_trade=best,
            worst_trade=worst,
            common_mistakes=common_mistakes,
        )

    def get_system_summary(self) -> dict[str, Any]:
        all_pnls = []
        for stats in self.agent_stats.values():
            all_pnls.extend(s["pnl"] for s in stats)

        grades = [r.grade for r in self.reviews]
        grade_dist = {g: grades.count(g) for g in ["A", "B", "C", "D", "F"]}

        return {
            "total_reviews": len(self.reviews),
            "total_pnl": sum(all_pnls),
            "avg_pnl": np.mean(all_pnls) if all_pnls else 0,
            "grade_distribution": grade_dist,
            "agents_tracked": list(self.agent_stats.keys()),
        }
