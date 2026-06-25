import pandas as pd
import streamlit as st
import yfinance as yf

from config import YF_ALIASES, GRAM_ALTIN_ALIASES
from database import normalize_symbol, cache_price, get_cached_price
from tefas_engine import get_tefas_latest_prices


def asset_type(tur):
    t = str(tur or "").strip()
    if t == "Fon":
        return "Fon"
    if "Hisse" in t:
        return "Hisse Senedi"
    if "Döviz" in t or "Doviz" in t:
        return "Döviz"
    if "Emtia" in t or "Altın" in t or "Altin" in t:
        return "Emtia"
    return t


def yf_symbol(symbol, typ):
    sym = normalize_symbol(symbol)
    if sym in YF_ALIASES:
        return YF_ALIASES[sym]
    if typ == "Hisse Senedi":
        return f"{sym}.IS"
    return sym


@st.cache_data(ttl=300)
def yf_latest(symbol, typ, lookback_days=15):
    sym = normalize_symbol(symbol)
    yfs = yf_symbol(sym, typ)
    try:
        df = yf.download(yfs, period=f"{lookback_days}d", auto_adjust=True, progress=False, threads=False)
        if df.empty:
            return None
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = close.dropna()
        if close.empty:
            return None
        price = float(close.iloc[-1])
        date = pd.Timestamp(close.index[-1]).strftime("%Y-%m-%d")
        return price, date, "Yahoo Finance"
    except Exception:
        return None


def get_price_table(portfolio):
    if portfolio.empty:
        return pd.DataFrame()

    df = portfolio.copy()
    df["symbol"] = df["kod_adi"].map(normalize_symbol)
    df["asset_type"] = df["tur"].map(asset_type)

    frames = []

    fonlar = tuple(df.loc[df["asset_type"] == "Fon", "symbol"].unique())
    if fonlar:
        fdf = get_tefas_latest_prices(fonlar)
        if not fdf.empty:
            frames.append(fdf)

    rows = []
    for _, row in df[df["asset_type"] != "Fon"][["symbol", "asset_type"]].drop_duplicates().iterrows():
        sym, typ = row["symbol"], row["asset_type"]

        result = yf_latest(sym, typ)
        if result:
            price, date, source = result
            cache_price(sym, typ, price, date, source)
            rows.append({
                "symbol": sym, "asset_type": typ, "price": price, "price_date": date,
                "source": source, "status": "live_or_last_close"
            })
        else:
            cached = get_cached_price(sym, typ)
            if cached:
                rows.append({
                    "symbol": sym, "asset_type": typ, "price": float(cached["price"]),
                    "price_date": cached["price_date"], "source": "SQLite cache",
                    "status": "cache_fallback"
                })

    # Gram altın: ONS ve USD verisinden hesapla
    try:
        usd = yf_latest("USD", "Döviz")
        ons = yf_latest("ONS", "Emtia")
        if usd and ons:
            gram = usd[0] * ons[0] / 31.1034768
            for alias in GRAM_ALTIN_ALIASES:
                rows.append({
                    "symbol": alias, "asset_type": "Emtia", "price": gram,
                    "price_date": max(usd[1], ons[1]), "source": "Yahoo Finance derived",
                    "status": "derived_last_close"
                })
    except Exception:
        pass

    if rows:
        frames.append(pd.DataFrame(rows))

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out["symbol"] = out["symbol"].map(normalize_symbol)
    return out.drop_duplicates(["symbol", "asset_type"], keep="last")
