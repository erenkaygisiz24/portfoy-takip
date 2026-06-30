import datetime as dt
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from google import genai
from pytefas import Crawler

from database import normalize_symbol
from providers import classify_asset_type, yf_symbol


# =========================
# INDICATORS
# =========================

def rsi(series, period=14):
    series = pd.to_numeric(series, errors="coerce").dropna()
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series):
    series = pd.to_numeric(series, errors="coerce").dropna()
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    return macd_line, signal, hist


def calculate_bollinger(series, period=20, std=2):
    series = pd.to_numeric(series, errors="coerce").dropna()
    middle = series.rolling(period).mean()
    deviation = series.rolling(period).std()
    upper = middle + std * deviation
    lower = middle - std * deviation
    return upper, middle, lower


# =========================
# HISTORY PROVIDERS
# =========================

@st.cache_data(ttl=3600, show_spinner=False)
def get_fund_history(symbol, days=180):
    symbol = normalize_symbol(symbol)
    try:
        crawler = Crawler()
        end = dt.date.today()
        start = end - dt.timedelta(days=int(days) + 20)

        df = crawler.fetch(
            start=start.isoformat(),
            end=end.isoformat(),
            columns="info",
        )

        if df is None or df.empty:
            return pd.Series(dtype=float)

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["fund_code"] = df["fund_code"].map(normalize_symbol)
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

        sub = df[df["fund_code"] == symbol].dropna(subset=["date", "price"])
        if sub.empty:
            return pd.Series(dtype=float)

        sub = sub.sort_values("date").tail(int(days))
        out = sub.set_index("date")["price"]
        out.index = pd.to_datetime(out.index).normalize()
        out.name = symbol
        return out

    except Exception as e:
        print("FUND HISTORY ERROR:", repr(e))
        return pd.Series(dtype=float)


@st.cache_data(ttl=3600, show_spinner=False)
def get_yahoo_history(symbol, asset_type, days=180):
    symbol = normalize_symbol(symbol)
    asset_type = classify_asset_type(asset_type)
    try:
        ticker = yf_symbol(symbol, asset_type)
        df = yf.download(
            ticker,
            period=f"{int(days)}d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if df is None or df.empty:
            return pd.Series(dtype=float)

        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        close = pd.to_numeric(close, errors="coerce").dropna()
        close.index = pd.to_datetime(close.index).normalize()
        close.name = symbol
        return close

    except Exception as e:
        print("YAHOO HISTORY ERROR:", repr(e))
        return pd.Series(dtype=float)


def get_asset_history(symbol, asset_type, days=180):
    asset_type = classify_asset_type(asset_type)
    if asset_type == "Fon":
        return get_fund_history(symbol, days)
    return get_yahoo_history(symbol, asset_type, days)


# =========================
# ANALYSIS
# =========================

def _status_from_rsi(value):
    if pd.isna(value):
        return "Yetersiz Veri"
    if value >= 70:
        return "Aşırı Alım"
    if value <= 30:
        return "Aşırı Satım"
    return "Nötr"


def _technical_signal(rsi_status, macd_status, trend, bollinger):
    if rsi_status == "Aşırı Satım" and macd_status == "Pozitif":
        return "🟢 Güçlü Al"
    if rsi_status == "Aşırı Alım":
        return "🟡 Kâr Realizasyonu"
    if trend.startswith("Yukarı") and macd_status == "Pozitif":
        return "🟢 Al"
    if macd_status == "Negatif" and trend.startswith("Zayıf"):
        return "🔴 Zayıf"
    if bollinger == "🟢 Alt Bant":
        return "🟢 Tepki Adayı"
    return "⚪ Bekle"


def _technical_score(last, ema20, rsi_status, macd_status, trend, bollinger):
    score = 50

    score += 15 if macd_status == "Pozitif" else -15
    score += 15 if trend.startswith("Yukarı") else -10

    if rsi_status == "Aşırı Satım":
        score += 10
    elif rsi_status == "Aşırı Alım":
        score -= 10

    score += 10 if last > ema20 else -5

    if bollinger == "🟢 Alt Bant":
        score += 10
    elif bollinger == "🔴 Üst Bant":
        score -= 5

    return int(max(0, min(100, score)))


def _score_comment(score):
    if score >= 75:
        return "🟢 Güçlü Pozitif"
    if score >= 55:
        return "🟡 Pozitif / Nötr"
    if score >= 35:
        return "🟠 Zayıf / Nötr"
    return "🔴 Negatif"


def analyze_asset(symbol, asset_type, days=180):
    symbol = normalize_symbol(symbol)
    asset_type = classify_asset_type(asset_type)
    price = get_asset_history(symbol, asset_type, days)

    if price.empty or len(price) < 20:
        return None

    last = float(price.iloc[-1])

    rsi_series = rsi(price)
    last_rsi = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else np.nan
    rsi_status = _status_from_rsi(last_rsi)

    macd_line, signal_line, hist_line = macd(price)
    last_macd = float(macd_line.iloc[-1])
    last_signal = float(signal_line.iloc[-1])
    macd_status = "Pozitif" if last_macd > last_signal else "Negatif"

    sma20 = float(price.rolling(20).mean().iloc[-1])
    sma50 = float(price.rolling(50).mean().iloc[-1]) if len(price) >= 50 else np.nan
    ema20 = float(price.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(price.ewm(span=50, adjust=False).mean().iloc[-1]) if len(price) >= 50 else np.nan

    upper, middle, lower = calculate_bollinger(price)
    upper_last = float(upper.iloc[-1])
    middle_last = float(middle.iloc[-1])
    lower_last = float(lower.iloc[-1])

    if pd.isna(sma50):
        trend = "Yukarı" if last > sma20 else "Zayıf / Aşağı"
    else:
        trend = "Yukarı" if last > sma20 > sma50 else "Zayıf / Aşağı"

    if last >= upper_last:
        bollinger = "🔴 Üst Bant"
    elif last <= lower_last:
        bollinger = "🟢 Alt Bant"
    else:
        bollinger = "⚪ Orta Bant"

    signal = _technical_signal(rsi_status, macd_status, trend, bollinger)
    support = float(price.tail(20).min())
    resistance = float(price.tail(20).max())
    score = _technical_score(last, ema20, rsi_status, macd_status, trend, bollinger)

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
        "Orta Bant": middle_last,
        "Alt Bant": lower_last,
        "Destek": support,
        "Direnç": resistance,
        "Teknik Skor": score,
        "Teknik Yorum": _score_comment(score),
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _analyze_single_cached(symbol, asset_type, days):
    return analyze_asset(symbol, asset_type, days)


def analyze_portfolio_technical(portfolio_df, days=180):
    rows = []
    if portfolio_df.empty:
        return pd.DataFrame()

    for _, row in portfolio_df.iterrows():
        result = _analyze_single_cached(row["kod_adi"], row["tur"], int(days))
        if result:
            rows.append(result)

    return pd.DataFrame(rows)


# =========================
# CHART DATA + FIGURES
# =========================

def get_technical_chart_data(symbol, asset_type, days=180):
    price = get_asset_history(symbol, asset_type, days)
    if price.empty or len(price) < 20:
        return pd.DataFrame()

    df = pd.DataFrame({"Fiyat": price})
    df["EMA20"] = price.ewm(span=20, adjust=False).mean()
    df["EMA50"] = price.ewm(span=50, adjust=False).mean()
    df["SMA20"] = price.rolling(20).mean()

    upper, middle, lower = calculate_bollinger(price)
    df["Bollinger Üst"] = upper
    df["Bollinger Orta"] = middle
    df["Bollinger Alt"] = lower
    df["RSI"] = rsi(price)
    macd_line, signal_line, hist_line = macd(price)
    df["MACD"] = macd_line
    df["MACD Sinyal"] = signal_line
    df["MACD Histogram"] = hist_line
    return df.dropna(how="all")


def build_technical_figures(chart_df, symbol):
    if chart_df.empty:
        return None, None, None

    price_fig = go.Figure()
    for col in ["Fiyat", "EMA20", "EMA50", "Bollinger Üst", "Bollinger Alt"]:
        if col in chart_df.columns:
            price_fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df[col], mode="lines", name=col))

    # Support / resistance as last 20-day min/max
    support = float(chart_df["Fiyat"].tail(20).min())
    resistance = float(chart_df["Fiyat"].tail(20).max())
    price_fig.add_hline(y=support, line_dash="dot", annotation_text="Destek")
    price_fig.add_hline(y=resistance, line_dash="dot", annotation_text="Direnç")
    price_fig.update_layout(title=f"{symbol} Fiyat + EMA + Bollinger", height=420, margin=dict(l=10, r=10, t=45, b=10))

    rsi_fig = go.Figure()
    rsi_fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["RSI"], mode="lines", name="RSI"))
    rsi_fig.add_hline(y=70, line_dash="dash", annotation_text="70")
    rsi_fig.add_hline(y=30, line_dash="dash", annotation_text="30")
    rsi_fig.update_layout(title="RSI", height=280, margin=dict(l=10, r=10, t=45, b=10))

    macd_fig = go.Figure()
    macd_fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["MACD"], mode="lines", name="MACD"))
    macd_fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["MACD Sinyal"], mode="lines", name="Sinyal"))
    macd_fig.add_trace(go.Bar(x=chart_df.index, y=chart_df["MACD Histogram"], name="Histogram"))
    macd_fig.update_layout(title="MACD", height=300, margin=dict(l=10, r=10, t=45, b=10))

    return price_fig, rsi_fig, macd_fig


# =========================
# COMMENTARY
# =========================

def technical_comment(row):
    return (
        f"{row['Kod']} için RSI {row['RSI']:.2f} seviyesinde ve durum {row['RSI Durumu']}. "
        f"MACD görünümü {row['MACD Durumu']}. Trend {row['Trend']}. "
        f"Bollinger konumu {row['Bollinger']}. Genel teknik sinyal {row['Teknik Sinyal']}. "
        f"Teknik skor {row['Teknik Skor']}/100: {row['Teknik Yorum']}."
    )


@st.cache_data(ttl=3600, show_spinner=False)
def technical_comment_with_gemini(row_dict):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return technical_comment(row_dict)

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
Aşağıdaki teknik analiz verisini yatırım tavsiyesi vermeden, kısa ve profesyonel yorumla.
En fazla 90 kelime yaz.

Veri:
{row_dict}

Format:
Teknik Görünüm:
Riskler:
İzlenecek Seviye:
"""
        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print("TECHNICAL GEMINI ERROR:", repr(e))
        return technical_comment(row_dict)
