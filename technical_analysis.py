import numpy as np
import pandas as pd
import yfinance as yf
from pytefas import Crawler
import streamlit as st


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def macd(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line, signal

@st.cache_data(ttl=3600)
def get_fund_history(symbol, days=180):
    import datetime as dt
    

    try:
        crawler = Crawler()

        end = dt.date.today()
        start = end - dt.timedelta(days=days + 10)

        df = crawler.fetch(
            start=start.isoformat(),
            end=end.isoformat(),
            columns="info",
        )

        if df is None or df.empty:
            return pd.Series(dtype=float)

        df["date"] = pd.to_datetime(df["date"])
        df["fund_code"] = df["fund_code"].astype(str).str.upper()
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

        df = df[df["fund_code"] == symbol.upper()]
        df = df.sort_values("date").tail(days)

        if df.empty:
            return pd.Series(dtype=float)

        return df.set_index("date")["price"]

    except Exception as e:
        print("FUND HISTORY ERROR:", e)
        return pd.Series(dtype=float)
def get_stock_history(symbol, days=180):
    try:
        ticker = symbol.upper()

        if not ticker.endswith(".IS"):
            ticker = ticker + ".IS"

        df = yf.download(
            ticker,
            period=f"{days}d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if df.empty:
            return pd.Series(dtype=float)

        close = df["Close"]

        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        return close.dropna()

    except Exception as e:
        print("STOCK HISTORY ERROR:", e)
        return pd.Series(dtype=float)


def get_asset_history(symbol, asset_type, days=180):
    if asset_type == "Fon":
        return get_fund_history(symbol, days)

    if asset_type == "Hisse Senedi":
        return get_stock_history(symbol, days)

    return pd.Series(dtype=float)


def analyze_asset(symbol, asset_type, days=180):
    price = get_asset_history(symbol, asset_type, days)

    if price.empty or len(price) < 20:
        return None

    last = float(price.iloc[-1])

    rsi_series = rsi(price)
    last_rsi = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else np.nan

    macd_line, signal_line = macd(price)
    upper, middle, lower = calculate_bollinger(price)

    upper_last = float(upper.iloc[-1])
    middle_last = float(middle.iloc[-1])
    lower_last = float(lower.iloc[-1])
    last_macd = float(macd_line.iloc[-1])
    last_signal = float(signal_line.iloc[-1])

    sma20 = float(price.rolling(20).mean().iloc[-1])
    sma50 = float(price.rolling(50).mean().iloc[-1]) if len(price) >= 50 else np.nan
    ema20 = float(price.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(price.ewm(span=50, adjust=False).mean().iloc[-1]) if len(price) >= 50 else np.nan
    if np.isnan(last_rsi):
        rsi_status = "Yetersiz Veri"
    elif last_rsi >= 70:
        rsi_status = "Aşırı Alım"
    elif last_rsi <= 30:
        rsi_status = "Aşırı Satım"
    else:
        rsi_status = "Nötr"

    macd_status = "Pozitif" if last_macd > last_signal else "Negatif"

    if np.isnan(sma50):
        trend = "Yukarı" if last > sma20 else "Aşağı"
    else:
        trend = "Yukarı" if last > sma20 > sma50 else "Zayıf / Aşağı"
    if last >= upper_last:
        bollinger = "🔴 Üst Bant"
    elif last <= lower_last:
        bollinger = "🟢 Alt Bant"
    else:
        bollinger = "⚪ Orta Bant"
    signal = "⚪ Bekle"

    if rsi_status == "Aşırı Satım" and macd_status == "Pozitif":
        signal = "🟢 Güçlü Al"
    elif rsi_status == "Aşırı Alım":
        signal = "🟡 Kâr Realizasyonu"
    elif trend.startswith("Yukarı") and macd_status == "Pozitif":
        signal = "🟢 Al"
    elif macd_status == "Negatif":
        signal = "🔴 Zayıf"

    print("SIGNAL:", symbol, signal)
    support = float(price.tail(20).min())
    resistance = float(price.tail(20).max())
    support = float(price.tail(20).min())
    resistance = float(price.tail(20).max())
    technical_score = 50
    
    if macd_status == "Pozitif":
        technical_score += 15
    else:
        technical_score -= 15

    if trend.startswith("Yukarı"):
        technical_score += 15
    else:
        technical_score -= 10

    if rsi_status == "Aşırı Satım":
        technical_score += 10
    elif rsi_status == "Aşırı Alım":
        technical_score -= 10

    if last > ema20:
        technical_score += 10
    else:
        technical_score -= 5

    if bollinger == "🟢 Alt Bant":
        technical_score += 10
    elif bollinger == "🔴 Üst Bant":
        technical_score -= 5

    technical_score = max(0, min(100, technical_score))

    if technical_score >= 75:
        technical_comment = "🟢 Güçlü Pozitif"
    elif technical_score >= 55:
        technical_comment = "🟡 Pozitif / Nötr"
    elif technical_score >= 35:
        technical_comment = "🟠 Zayıf / Nötr"
    else:
        technical_comment = "🔴 Negatif"
    return {
        "Kod": symbol,
        "Tür": asset_type,
        "Son Fiyat": last,
        "RSI": last_rsi,
        "RSI Durumu": rsi_status,
        "MACD": last_macd,
        "MACD Sinyal": last_signal,
        "MACD Durumu": macd_status,
        "SMA20": sma20,
        "SMA50": sma50,
        "EMA20": ema20,
        "EMA50": ema50,
        "Trend": trend,
        "Teknik Sinyal": signal,
        "Bollinger": bollinger,
        "Üst Bant": upper_last,
        "Alt Bant": lower_last,
        "Destek": support,
        "Direnç": resistance,
        "Teknik Skor": technical_score,
        "Teknik Yorum": technical_comment,
    }
def analyze_portfolio_technical(portfolio_df, days=180):
    rows = []

    for _, row in portfolio_df.iterrows():
        result = analyze_asset(row["kod_adi"], row["tur"], days)

        if result:
            rows.append(result)

    return pd.DataFrame(rows)
def calculate_bollinger(series, period=20, std=2):
    middle = series.rolling(period).mean()
    deviation = series.rolling(period).std()

    upper = middle + std * deviation
    lower = middle - std * deviation

    return upper, middle, lower