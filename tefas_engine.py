import datetime as dt
import pandas as pd
import requests
import streamlit as st

from config import TEFAS_URL, HEADERS
from database import normalize_symbol, cache_price, get_cached_price


def parse_float(value):
    if value is None:
        return None
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def tr_date(date_obj):
    return date_obj.strftime("%d.%m.%Y")


@st.cache_data(ttl=900)
def fetch_tefas_by_date(date_text):
    try:
        response = requests.post(
            TEFAS_URL,
            headers=HEADERS,
            data={"fontip": "YAT", "bastarih": date_text, "bittarih": date_text},
            timeout=15,
        )
        response.raise_for_status()
        df = pd.DataFrame(response.json())
        if df.empty or "FONKODU" not in df.columns or "FIYAT" not in df.columns:
            return pd.DataFrame()

        df["symbol"] = df["FONKODU"].map(normalize_symbol)
        df["price"] = df["FIYAT"].map(parse_float)
        df["price_date"] = pd.to_datetime(date_text, dayfirst=True).strftime("%Y-%m-%d")
        return df.dropna(subset=["symbol", "price"])[["symbol", "price", "price_date"]]
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900)
def get_tefas_latest_prices(symbols, lookback_days=15):
    symbols = tuple(sorted({normalize_symbol(s) for s in symbols if normalize_symbol(s)}))
    rows, found = [], set()
    if not symbols:
        return pd.DataFrame()

    today = dt.date.today()
    for i in range(lookback_days):
        date_text = tr_date(today - dt.timedelta(days=i))
        df = fetch_tefas_by_date(date_text)
        if df.empty:
            continue
        df = df[df["symbol"].isin(symbols)]
        for _, row in df.iterrows():
            sym = row["symbol"]
            if sym in found:
                continue
            price = float(row["price"])
            cache_price(sym, "Fon", price, row["price_date"], "TEFAS")
            rows.append({
                "symbol": sym, "asset_type": "Fon", "price": price,
                "price_date": row["price_date"], "source": "TEFAS",
                "status": "live_or_last_close"
            })
            found.add(sym)
        if len(found) == len(symbols):
            break

    for sym in symbols:
        if sym not in found:
            cached = get_cached_price(sym, "Fon")
            if cached:
                rows.append({
                    "symbol": sym, "asset_type": "Fon", "price": float(cached["price"]),
                    "price_date": cached["price_date"], "source": "SQLite cache",
                    "status": "cache_fallback"
                })
    return pd.DataFrame(rows)
