import numpy as np
import pandas as pd

from market_engine import get_history_matrix
from optimizer import optimize_portfolio


def analytics_from_portfolio(portfolio):
    prices = get_history_matrix(portfolio, days=365)
    if prices.empty or prices.shape[1] < 2:
        return None, None, prices

    returns = prices.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="all")
    returns = returns.dropna(axis=1, how="all")

    if returns.empty or returns.shape[1] < 2:
        return None, None, prices

    corr = returns.corr()
    summary = pd.DataFrame({
        "Yıllık Getiri": returns.mean() * 252,
        "Yıllık Volatilite": returns.std() * np.sqrt(252),
        "Son Fiyat": prices.iloc[-1],
    })
    optimal = optimize_portfolio(returns)
    summary.attrs["optimal"] = optimal
    return corr, summary, prices
