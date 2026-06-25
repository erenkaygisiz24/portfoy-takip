import datetime as dt

import pandas as pd
import yfinance as yf

from database import normalize_symbol
from providers import ProviderManager, classify_asset_type, yf_symbol


def get_price_table(portfolio):
    if portfolio.empty:
        return pd.DataFrame()

    manager = ProviderManager()
    return manager.get_prices_for_portfolio(portfolio)


def asset_type(tur):
    return classify_asset_type(tur)


def get_history_matrix(portfolio, days=365):
    if portfolio.empty:
        return pd.DataFrame()

    df = portfolio.copy()
    df["symbol"] = df["kod_adi"].map(normalize_symbol)
    df["asset_type"] = df["tur"].map(classify_asset_type)

    end = dt.date.today()
    start = end - dt.timedelta(days=int(days) + 10)

    symbol_map = {
        row["symbol"]: yf_symbol(row["symbol"], row["asset_type"])
        for _, row in df[df["asset_type"] != "Fon"].drop_duplicates(["symbol", "asset_type"]).iterrows()
    }

    if not symbol_map:
        return pd.DataFrame()

    try:
        raw = yf.download(
            sorted(set(symbol_map.values())),
            start=start.isoformat(),
            end=(end + dt.timedelta(days=1)).isoformat(),
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker",
        )
    except Exception:
        return pd.DataFrame()

    out = {}
    tickers = sorted(set(symbol_map.values()))
    for original, ticker in symbol_map.items():
        try:
            if len(tickers) == 1:
                close = raw["Close"]
            elif isinstance(raw.columns, pd.MultiIndex):
                close = raw[ticker]["Close"]
            else:
                close = raw["Close"]

            close = close.dropna()
            if not close.empty:
                close.index = pd.to_datetime(close.index).normalize()
                out[original] = close
        except Exception:
            continue

    if not out:
        return pd.DataFrame()

    return pd.DataFrame(out).sort_index().ffill().tail(days)
