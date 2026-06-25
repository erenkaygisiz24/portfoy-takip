import numpy as np
import pandas as pd
from scipy.optimize import minimize


def portfolio_return(weights, mean_returns):
    return np.sum(mean_returns * weights)


def portfolio_volatility(weights, cov_matrix):
    return np.sqrt(weights.T @ cov_matrix @ weights)


def negative_sharpe(weights, mean_returns, cov_matrix, rf=0.0):
    r = portfolio_return(weights, mean_returns)
    v = portfolio_volatility(weights, cov_matrix)
    if v == 0:
        return 1e9
    return -(r - rf) / v


def optimize_portfolio(returns):
    mean_returns = returns.mean() * 252
    cov_matrix = returns.cov() * 252

    n = len(mean_returns)

    constraints = ({
        "type": "eq",
        "fun": lambda w: np.sum(w) - 1
    },)

    bounds = tuple((0, 1) for _ in range(n))

    initial = np.repeat(1 / n, n)

    result = minimize(
        negative_sharpe,
        initial,
        args=(mean_returns, cov_matrix),
        bounds=bounds,
        constraints=constraints,
    )

    return pd.DataFrame({
        "Varlık": mean_returns.index,
        "Optimal Ağırlık": result.x
    })