from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp


@dataclass
class FundamentalScore:
    value: float
    growth: float
    quality: float
    momentum: float

    @property
    def total(self) -> float:
        return (self.value + self.growth + self.quality + self.momentum) / 4.0


@dataclass
class DividendInfo:
    ticker: str
    last_dividend: float
    dividend_yield: float
    next_ex_date: Optional[str] = None
    next_payment_date: Optional[str] = None


@dataclass
class FundamentalData:
    ticker: str
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    sector: Optional[str] = None
    fetched_at: float = field(default_factory=time.time)


@dataclass
class SectorComparison:
    ticker: str
    sector: str
    pe_vs_sector: Optional[float] = None
    pb_vs_sector: Optional[float] = None
    yield_vs_sector: Optional[float] = None


class FundamentalAnalyzer:
    MOEX_ISS_BASE = "https://iss.moex.com/iss"

    def __init__(self, cache_ttl: int = 3600) -> None:
        self._cache: dict[str, FundamentalData] = {}
        self._cache_ttl = cache_ttl

    def _is_cached(self, ticker: str) -> bool:
        if ticker not in self._cache:
            return False
        return (time.time() - self._cache[ticker].fetched_at) < self._cache_ttl

    async def _get_json(self, url: str) -> Any:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"iss.json": "extended", "iss.meta": "off"}) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)

    async def fetch_moex_data(self, ticker: str) -> FundamentalData:
        if self._is_cached(ticker):
            return self._cache[ticker]

        url = f"{self.MOEX_ISS_BASE}/securities/{ticker}.json"
        data = await self._get_json(url)

        fd = FundamentalData(ticker=ticker)

        try:
            description = data[1]["description"]
            desc_map: dict[str, str] = {}
            for item in description:
                desc_map[item["name"]] = item["value"]
            fd.sector = desc_map.get("TYPENAME")
        except (KeyError, IndexError, TypeError):
            pass

        market_url = f"{self.MOEX_ISS_BASE}/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
        market_data = await self._get_json(market_url)

        try:
            md = market_data[1]["marketdata"]
            if md:
                row = md[0]
                last_price = row.get("LAST")
                if last_price:
                    fd.market_cap = last_price * row.get("ISSUESIZE", 0)

            securities = market_data[1]["securities"]
            if securities:
                sec_row = securities[0]
                fd.pe_ratio = sec_row.get("PE")
                fd.pb_ratio = sec_row.get("PB")
                fd.dividend_yield = sec_row.get("DIVIDENDYIELD")
        except (KeyError, IndexError, TypeError):
            pass

        fd.fetched_at = time.time()
        self._cache[ticker] = fd
        return fd

    async def compare_sector(self, ticker: str) -> SectorComparison:
        fd = await self.fetch_moex_data(ticker)
        sector = fd.sector or "Unknown"

        index_url = f"{self.MOEX_ISS_BASE}/engines/stock/markets/shares/boards/TQBR/securities.json"
        data = await self._get_json(index_url)

        sector_pe: list[float] = []
        sector_pb: list[float] = []
        sector_yield: list[float] = []

        try:
            securities = data[1]["securities"]
            for sec in securities:
                pe = sec.get("PE")
                pb = sec.get("PB")
                dy = sec.get("DIVIDENDYIELD")
                if pe and pe > 0:
                    sector_pe.append(pe)
                if pb and pb > 0:
                    sector_pb.append(pb)
                if dy and dy > 0:
                    sector_yield.append(dy)
        except (KeyError, IndexError, TypeError):
            pass

        avg_pe = sum(sector_pe) / len(sector_pe) if sector_pe else None
        avg_pb = sum(sector_pb) / len(sector_pb) if sector_pb else None
        avg_yield = sum(sector_yield) / len(sector_yield) if sector_yield else None

        return SectorComparison(
            ticker=ticker,
            sector=sector,
            pe_vs_sector=(fd.pe_ratio / avg_pe) if fd.pe_ratio and avg_pe else None,
            pb_vs_sector=(fd.pb_ratio / avg_pb) if fd.pb_ratio and avg_pb else None,
            yield_vs_sector=(fd.dividend_yield / avg_yield) if fd.dividend_yield and avg_yield else None,
        )

    async def dividend_calendar(self, tickers: list[str]) -> list[DividendInfo]:
        results: list[DividendInfo] = []
        for ticker in tickers:
            url = f"{self.MOEX_ISS_BASE}/securities/{ticker}/dividends.json"
            try:
                data = await self._get_json(url)
                dividends = data[1].get("dividends", [])
                if dividends:
                    latest = dividends[-1]
                    results.append(
                        DividendInfo(
                            ticker=ticker,
                            last_dividend=float(latest.get("value", 0)),
                            dividend_yield=float(latest.get("valueprc", 0)),
                            next_ex_date=latest.get("registryclosedate"),
                            next_payment_date=latest.get("paymentdate"),
                        )
                    )
            except Exception:
                continue
        return results

    async def score(self, ticker: str) -> FundamentalScore:
        fd = await self.fetch_moex_data(ticker)
        comparison = await self.compare_sector(ticker)

        value_score = 50.0
        if comparison.pe_vs_sector is not None:
            if comparison.pe_vs_sector < 0.8:
                value_score = 80.0
            elif comparison.pe_vs_sector < 1.0:
                value_score = 65.0
            elif comparison.pe_vs_sector > 1.5:
                value_score = 25.0
            else:
                value_score = 45.0

        growth_score = 50.0
        if fd.pe_ratio is not None:
            if fd.pe_ratio < 0:
                growth_score = 20.0
            elif fd.pe_ratio < 10:
                growth_score = 70.0
            elif fd.pe_ratio < 20:
                growth_score = 55.0
            else:
                growth_score = 35.0

        quality_score = 50.0
        if fd.pb_ratio is not None:
            if fd.pb_ratio < 1.0:
                quality_score = 70.0
            elif fd.pb_ratio < 2.0:
                quality_score = 55.0
            else:
                quality_score = 35.0

        momentum_score = 50.0
        if fd.dividend_yield is not None:
            if fd.dividend_yield > 8.0:
                momentum_score = 80.0
            elif fd.dividend_yield > 5.0:
                momentum_score = 65.0
            elif fd.dividend_yield > 2.0:
                momentum_score = 50.0
            else:
                momentum_score = 35.0

        return FundamentalScore(
            value=min(100.0, max(0.0, value_score)),
            growth=min(100.0, max(0.0, growth_score)),
            quality=min(100.0, max(0.0, quality_score)),
            momentum=min(100.0, max(0.0, momentum_score)),
        )
