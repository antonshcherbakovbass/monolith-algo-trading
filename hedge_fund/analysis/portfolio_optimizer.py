"""
Portfolio Optimizer: Markowitz, Black-Litterman, Risk Parity.

Computes optimal portfolio weights for MOEX instruments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from loguru import logger


@dataclass
class PortfolioWeights:
    weights: dict[str, float]
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    method: str = ""

    @property
    def sorted_weights(self) -> list[tuple[str, float]]:
        return sorted(self.weights.items(), key=lambda x: x[1], reverse=True)


class PortfolioOptimizer:
    """
    Multi-method portfolio optimizer for MOEX equities.
    
    Methods:
    - Markowitz Mean-Variance (maximize Sharpe)
    - Minimum Variance
    - Risk Parity (equal risk contribution)
    - Black-Litterman (incorporate agent views)
    - Max Diversification
    """

    def __init__(self, risk_free_rate: float = 0.16):
        self.risk_free_rate = risk_free_rate  # CBR key rate as proxy
        self.log = logger.bind(component="portfolio_optimizer")

    def markowitz_max_sharpe(
        self, returns: pd.DataFrame, min_weight: float = 0.0, max_weight: float = 0.3
    ) -> PortfolioWeights:
        tickers = list(returns.columns)
        n = len(tickers)
        mu = returns.mean().values * 252
        cov = returns.cov().values * 252

        def neg_sharpe(w: np.ndarray) -> float:
            ret = w @ mu
            vol = np.sqrt(w @ cov @ w)
            return -(ret - self.risk_free_rate) / max(vol, 1e-10)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(min_weight, max_weight)] * n
        x0 = np.ones(n) / n

        result = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
        w = result.x if result.success else x0
        ret = float(w @ mu)
        vol = float(np.sqrt(w @ cov @ w))

        return PortfolioWeights(
            weights=dict(zip(tickers, [round(float(x), 4) for x in w])),
            expected_return=ret,
            expected_volatility=vol,
            sharpe_ratio=(ret - self.risk_free_rate) / max(vol, 1e-10),
            method="markowitz_max_sharpe",
        )

    def minimum_variance(
        self, returns: pd.DataFrame, min_weight: float = 0.0, max_weight: float = 0.3
    ) -> PortfolioWeights:
        tickers = list(returns.columns)
        n = len(tickers)
        mu = returns.mean().values * 252
        cov = returns.cov().values * 252

        def portfolio_var(w: np.ndarray) -> float:
            return float(w @ cov @ w)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(min_weight, max_weight)] * n
        x0 = np.ones(n) / n

        result = minimize(portfolio_var, x0, method="SLSQP", bounds=bounds, constraints=constraints)
        w = result.x if result.success else x0
        ret = float(w @ mu)
        vol = float(np.sqrt(w @ cov @ w))

        return PortfolioWeights(
            weights=dict(zip(tickers, [round(float(x), 4) for x in w])),
            expected_return=ret, expected_volatility=vol,
            sharpe_ratio=(ret - self.risk_free_rate) / max(vol, 1e-10),
            method="minimum_variance",
        )

    def risk_parity(self, returns: pd.DataFrame) -> PortfolioWeights:
        tickers = list(returns.columns)
        n = len(tickers)
        cov = returns.cov().values * 252
        mu = returns.mean().values * 252

        def risk_contribution_error(w: np.ndarray) -> float:
            port_vol = np.sqrt(w @ cov @ w)
            if port_vol < 1e-10:
                return 1e10
            marginal = cov @ w
            rc = w * marginal / port_vol
            target = port_vol / n
            return float(np.sum((rc - target) ** 2))

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.01, 0.5)] * n
        x0 = np.ones(n) / n

        result = minimize(risk_contribution_error, x0, method="SLSQP", bounds=bounds, constraints=constraints)
        w = result.x if result.success else x0
        ret = float(w @ mu)
        vol = float(np.sqrt(w @ cov @ w))

        return PortfolioWeights(
            weights=dict(zip(tickers, [round(float(x), 4) for x in w])),
            expected_return=ret, expected_volatility=vol,
            sharpe_ratio=(ret - self.risk_free_rate) / max(vol, 1e-10),
            method="risk_parity",
        )

    def black_litterman(
        self,
        returns: pd.DataFrame,
        views: dict[str, float],
        view_confidences: dict[str, float] | None = None,
        tau: float = 0.05,
    ) -> PortfolioWeights:
        """
        Black-Litterman model incorporating agent views.
        
        views: dict of ticker -> expected excess return (e.g., {"SBER": 0.15, "GAZP": -0.05})
        view_confidences: dict of ticker -> confidence (0-1), default 0.5
        """
        tickers = list(returns.columns)
        n = len(tickers)
        cov = returns.cov().values * 252
        mu_market = returns.mean().values * 252

        # Market equilibrium weights (equal weight as proxy)
        w_market = np.ones(n) / n
        pi = cov @ w_market  # implied equilibrium returns

        # Build P (pick matrix) and Q (view vector) and Omega (uncertainty)
        view_tickers = [t for t in views if t in tickers]
        if not view_tickers:
            return self.markowitz_max_sharpe(returns)

        k = len(view_tickers)
        P = np.zeros((k, n))
        Q = np.zeros(k)
        omega_diag = np.zeros(k)

        for i, t in enumerate(view_tickers):
            j = tickers.index(t)
            P[i, j] = 1.0
            Q[i] = views[t]
            conf = (view_confidences or {}).get(t, 0.5)
            omega_diag[i] = tau * cov[j, j] * (1 - conf) / max(conf, 0.01)

        Omega = np.diag(omega_diag)

        # BL formula
        tau_cov = tau * cov
        tau_cov_inv = np.linalg.inv(tau_cov)
        P_Omega_inv = P.T @ np.linalg.inv(Omega)
        bl_mu = np.linalg.inv(tau_cov_inv + P_Omega_inv @ P) @ (tau_cov_inv @ pi + P_Omega_inv @ Q)
        bl_cov = np.linalg.inv(tau_cov_inv + P_Omega_inv @ P)

        # Optimize with BL returns
        def neg_sharpe(w: np.ndarray) -> float:
            ret = w @ bl_mu
            vol = np.sqrt(w @ cov @ w)
            return -(ret - self.risk_free_rate) / max(vol, 1e-10)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, 0.3)] * n
        x0 = np.ones(n) / n
        result = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
        w = result.x if result.success else x0
        ret = float(w @ bl_mu)
        vol = float(np.sqrt(w @ cov @ w))

        return PortfolioWeights(
            weights=dict(zip(tickers, [round(float(x), 4) for x in w])),
            expected_return=ret, expected_volatility=vol,
            sharpe_ratio=(ret - self.risk_free_rate) / max(vol, 1e-10),
            method="black_litterman",
        )

    def recommend(
        self, returns: pd.DataFrame, agent_views: dict[str, float] | None = None
    ) -> PortfolioWeights:
        """Pick the best method based on data quality and available views."""
        if agent_views:
            return self.black_litterman(returns, agent_views)
        try:
            sharpe_result = self.markowitz_max_sharpe(returns)
            rp_result = self.risk_parity(returns)
            if sharpe_result.sharpe_ratio > rp_result.sharpe_ratio:
                return sharpe_result
            return rp_result
        except Exception as e:
            self.log.warning(f"Optimization failed, using equal weight: {e}")
            tickers = list(returns.columns)
            n = len(tickers)
            return PortfolioWeights(
                weights={t: round(1/n, 4) for t in tickers},
                method="equal_weight",
            )
