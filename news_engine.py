import os
import datetime as dt

import feedparser
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from google import genai

from database import normalize_symbol


FUND_NAMES = {
    "IHK": "İş Portföy İş'te Kadın Hisse Senedi Fonu",
    "YAY": "Yapı Kredi Portföy Yabancı Teknoloji Fonu",
}


def analyze_news_ai(items, symbol):
    if not items:
        return {
            "symbol": symbol,
            "summary": f"{symbol} için haber bulunamadı.",
            "sentiment": "Nötr",
            "importance": "1",
            "impact": "Veri yok.",
        }

    text = " ".join(str(x.get("title", "")) for x in items).lower()

    negative = ["zarar", "ceza", "dava", "iptal", "düşüş", "risk", "soruşturma", "uyarı"]
    positive = ["kar", "kâr", "artış", "büyüme", "anlaşma", "yatırım", "getiri", "yükseliş"]
    important = ["kap", "portföy", "strateji", "yönetim", "birleşme", "tasfiye", "temettü", "özel durum"]

    neg_score = sum(w in text for w in negative)
    pos_score = sum(w in text for w in positive)
    imp_score = sum(w in text for w in important)

    if pos_score > neg_score:
        sentiment = "Pozitif 🟢"
    elif neg_score > pos_score:
        sentiment = "Negatif 🔴"
    else:
        sentiment = "Nötr 🟡"

    importance = max(1, min(5, imp_score + 1))
    top_title = items[0].get("title", "")

    if neg_score > 0:
        impact = "Risk sinyali olabilir."
    elif pos_score > 0:
        impact = "Olumlu haber akışı izlenebilir."
    else:
        impact = "Belirgin güçlü bir sinyal yok."

    summary = f"""
📝 Özet:
{symbol} için {len(items)} haber/KAP başlığı bulundu. Öne çıkan başlık: {top_title}

😊 Duygu:
{sentiment}

⭐ Önem:
{importance}

📈 Portföy Etkisi:
{impact}
"""

    return {
        "symbol": symbol,
        "summary": summary,
        "sentiment": sentiment,
        "importance": str(importance),
        "impact": impact,
    }


@st.cache_data(ttl=3600)
def analyze_news_with_llm_cached(titles_text, symbol):
    items = [{"title": t.strip("- ").strip()} for t in titles_text.splitlines() if t.strip()]
    fallback = analyze_news_ai(items, symbol)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""
Sen profesyonel bir finans haber analistisin.

Fon kodu: {symbol}

Haber/KAP başlıkları:
{titles_text}

Görev:
Bu haberlerin portföy yatırımcısı açısından ne anlama geldiğini kısa analiz et.

Kurallar:
- Fonun genel tanımını yapma.
- Yatırım tavsiyesi verme.
- En fazla 90 kelime yaz.
- Sadece haber akışının olası etkisini yorumla.
- Eğer haber sadece "Fon Detay", "Fon Bilgileri", "PDP", "KAP" genel sayfası veya tanıtım sayfası ise yeni gelişme olmadığını belirt.
- Böyle bir durumda portföy etkisini Düşük yaz.

Şu formatta cevap ver:

📝 Özet:
...

😊 Duygu:
Pozitif / Nötr / Negatif

⭐ Önem:
1-5

📈 Portföy Etkisi:
Düşük / Orta / Yüksek
"""

        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=prompt,
        )

        return {
            "symbol": symbol,
            "summary": response.text.strip(),
            "sentiment": "Gemini AI",
            "importance": "AI",
            "impact": "Gemini tarafından analiz edildi.",
        }

    except Exception as e:
        print("GEMINI ERROR:", repr(e))
        return fallback


def google_news_search(symbol, fund_name=None, limit=10):
    symbol = normalize_symbol(symbol)

    queries = [
        f"{symbol} fon",
        f"{symbol} KAP",
        f"{symbol} TEFAS",
    ]

    if fund_name:
        queries.append(fund_name)

    if symbol in FUND_NAMES:
        queries.append(FUND_NAMES[symbol])
        queries.append(f"{FUND_NAMES[symbol]} KAP")
        queries.append(f"{FUND_NAMES[symbol]} haber")
        queries.append(f"{FUND_NAMES[symbol]} Bloomberght")

    rows = []

    for q in queries:
        url = (
            "https://news.google.com/rss/search?"
            f"q={requests.utils.quote(q)}&hl=tr&gl=TR&ceid=TR:tr"
        )

        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:limit]:
                title = entry.get("title", "")
                if not title:
                    continue

                rows.append({
                    "source": "Google News",
                    "symbol": symbol,
                    "title": title,
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                    "type": "Haber",
                })

        except Exception as e:
            print("GOOGLE NEWS ERROR:", e)

    return rows[:limit]


def kap_google_search(symbol, limit=10):
    symbol = normalize_symbol(symbol)

    queries = [
        f"{symbol} site:kap.org.tr",
        f"{symbol} kap.org.tr",
    ]

    if symbol in FUND_NAMES:
        queries.append(f"{FUND_NAMES[symbol]} site:kap.org.tr")

    rows = []

    for q in queries:
        url = (
            "https://news.google.com/rss/search?"
            f"q={requests.utils.quote(q)}&hl=tr&gl=TR&ceid=TR:tr"
        )

        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:limit]:
                title = entry.get("title", "")
                if not title:
                    continue

                rows.append({
                    "source": "KAP",
                    "symbol": symbol,
                    "title": title,
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                    "type": "KAP",
                })

        except Exception as e:
            print("KAP GOOGLE ERROR:", e)

    return rows[:limit]


def mynet_kap_search(symbol, limit=5):
    symbol = normalize_symbol(symbol)
    url = "https://finans.mynet.com/borsa/kaphaberleri/"
    rows = []

    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        text_items = soup.find_all(["a", "li", "p", "div"])

        for item in text_items:
            text = " ".join(item.get_text(" ", strip=True).split())
            if not text:
                continue

            if symbol.upper() in text.upper():
                link = item.get("href", "")
                if link and link.startswith("/"):
                    link = "https://finans.mynet.com" + link

                rows.append({
                    "source": "Mynet KAP",
                    "symbol": symbol,
                    "title": text[:300],
                    "published": "",
                    "link": link,
                    "type": "KAP",
                })

            if len(rows) >= limit:
                break

    except Exception as e:
        print("MYNET KAP ERROR:", e)

    return rows


def get_symbol_news(symbol, fund_name=None, days=30):
    symbol = normalize_symbol(symbol)

    rows = []
    rows.extend(google_news_search(symbol, fund_name=fund_name, limit=10))
    rows.extend(kap_google_search(symbol, limit=10))
    rows.extend(mynet_kap_search(symbol, limit=5))

    df = pd.DataFrame(rows)

    if df.empty:
        return df, analyze_news_ai([], symbol)

    df = df.drop_duplicates(subset=["title"]).reset_index(drop=True)

    if symbol == "IHK":
        df = df[
            df["title"].str.contains(
                "Fon|Portföy|İş Portföy|TEFAS|Hisse|Kadın|Yatırım Fonu|Bloomberght",
                case=False,
                na=False,
                regex=True
            )
        ].reset_index(drop=True)

    df["published_dt"] = pd.to_datetime(df["published"], errors="coerce")

    if days and days < 3650:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df = df[
            df["published_dt"].isna() |
            (df["published_dt"] >= cutoff)
        ]

    if df.empty:
        return df.drop(columns=["published_dt"], errors="ignore"), analyze_news_ai([], symbol)

    df = df.sort_values("published_dt", ascending=False)
    df = df.drop(columns=["published_dt"], errors="ignore")

    titles_text = "\n".join(
        f"- {title}" for title in df["title"].head(5).tolist()
    )

    analysis = analyze_news_with_llm_cached(titles_text, symbol)

    return df, analysis


def get_portfolio_news(portfolio_df, days=30):
    all_rows = []
    summaries = []

    if portfolio_df.empty:
        return pd.DataFrame(), []

    for _, row in portfolio_df.iterrows():
        symbol = normalize_symbol(row["kod_adi"])

        fund_name = None
        if "fon_adi" in portfolio_df.columns:
            fund_name = row.get("fon_adi")

        df, analysis = get_symbol_news(symbol, fund_name=fund_name, days=days)

        if not df.empty:
            all_rows.append(df)

        summaries.append(analysis)

    if all_rows:
        news_df = pd.concat(all_rows, ignore_index=True)
        news_df = news_df.drop_duplicates(subset=["title"]).reset_index(drop=True)
    else:
        news_df = pd.DataFrame()

    return news_df, summaries