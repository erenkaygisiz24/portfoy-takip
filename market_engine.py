import pandas as pd

from database import normalize_symbol
from providers import ProviderManager, classify_asset_type


def get_price_table(portfolio):
    if portfolio.empty:
        return pd.DataFrame()

    manager = ProviderManager()
    return manager.get_prices_for_portfolio(portfolio)


def asset_type(tur):
    return classify_asset_type(tur)


def yf_symbol(symbol, typ):
    from providers import yf_symbol as _yf_symbol
    return _yf_symbol(normalize_symbol(symbol), typ)
