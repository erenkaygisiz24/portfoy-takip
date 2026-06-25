import numpy as np
import pandas as pd

from database import normalize_symbol
from market_engine import get_price_table, asset_type


def value_portfolio(portfolio):
    if portfolio.empty:
        return portfolio.copy(), pd.DataFrame()

    df = portfolio.copy()
    df["symbol"] = df["kod_adi"].map(normalize_symbol)
    df["asset_type"] = df["tur"].map(asset_type)

    prices = get_price_table(df)

    if prices.empty:
        df["price"] = df["maliyet"]
        df["price_date"] = "-"
        df["source"] = "Maliyet fallback"
        df["status"] = "cost_fallback"
    else:
        df = df.merge(prices, on=["symbol", "asset_type"], how="left")
        missing = df["price"].isna()
        df.loc[missing, "price"] = df.loc[missing, "maliyet"]
        df.loc[missing, "price_date"] = "-"
        df.loc[missing, "source"] = "Maliyet fallback"
        df.loc[missing, "status"] = "cost_fallback"

    for col in ["adet", "maliyet", "price", "ideal_oran", "hedef_fiyat"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["maliyet_degeri"] = df["adet"] * df["maliyet"]
    df["guncel_deger"] = df["adet"] * df["price"]
    df["kar_zarar"] = df["guncel_deger"] - df["maliyet_degeri"]
    df["kar_zarar_pct"] = np.where(df["maliyet_degeri"] > 0, df["kar_zarar"] / df["maliyet_degeri"], 0)

    total = df["guncel_deger"].sum()
    df["portfoy_orani"] = np.where(total > 0, df["guncel_deger"] / total, 0)
    df["hedef_sapma"] = df["portfoy_orani"] - df["ideal_oran"]

    return df, prices


def rebalance_table(valued):
    if valued.empty:
        return pd.DataFrame()

    total = float(valued["guncel_deger"].sum())
    df = valued.copy()
    df["hedef_tutar"] = total * df["ideal_oran"]
    df["alim_satim_tutari"] = df["hedef_tutar"] - df["guncel_deger"]
    df["tahmini_adet"] = np.where(df["price"] > 0, df["alim_satim_tutari"] / df["price"], 0)
    return df
