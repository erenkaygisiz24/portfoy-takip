import datetime as dt
import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup

from database import normalize_symbol
from openai import OpenAI


def analyze_news_ai(items, symbol):
    if not items:
        return {
            "symbol": symbol,
            "summary": f"{symbol} için haber bulunamadı.",
            "sentiment": "Nötr",
            "importance": "⭐",
            "impact": "Veri yok",
        }

    text = " ".join([str(x.get("title", "")) for x in items]).lower()

    negative = ["zarar", "ceza", "dava", "iptal", "düşüş", "risk", "soruşturma", "uyarı"]
    positive = ["kar", "kâr", "artış", "büyüme", "anlaşma", "yatırım", "getiri", "yükseliş"]
    important = ["kap", "portföy", "strateji", "yönetim", "birleşme", "tasfiye", "temettü"]

    neg_score = sum(w in text for w in negative)
    pos_score = sum(w in text for w in positive)
    imp_score = sum(w in text for w in important)

    if pos_score > neg_score:
        sentiment = "Pozitif 🟢"
    elif neg_score > pos_score:
        sentiment = "Negatif 🔴"
    else:
        sentiment = "Nötr 🟡"

    importance = "⭐" * max(1, min(5, imp_score + 1))

    top_title = items[0].get("title", "")

    summary = (
        f"{symbol} için {len(items)} haber bulundu. "
        f"Genel duygu: {sentiment}. "
        f"Öne çıkan başlık: {top_title}"
    )

    if neg_score > 0:
        impact = "Risk sinyali olabilir, detaylı inceleme önerilir."
    elif pos_score > 0:
        impact = "Olumlu haber akışı var, portföy etkisi izlenebilir."
    else:
        impact = "Belirgin olumlu/olumsuz sinyal yok."

    return {
        "symbol": symbol,
        "summary": summary,
        "sentiment": sentiment,
        "importance": importance,
        "impact": impact,
    }
def analyze_news_with_llm(items, symbol):
    try:
        client = OpenAI()

        text = "\n".join(
            [f"- {x.get('title', '')}" for x in items[:10]]
        )

        prompt = f"""
Aşağıdaki haber başlıklarını {symbol} fonu açısından analiz et.

Başlıklar:
{text}

Çıktı formatı:
Özet:
Duygu:
Önem:
Portföy Etkisi:
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen finansal haberleri kısa, net ve yatırımcı odaklı özetleyen bir asistansın."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        content = response.choices[0].message.content

        return {
            "symbol": symbol,
            "summary": content,
            "sentiment": "AI Analizi",
            "importance": "AI",
            "impact": "AI tarafından yorumlandı.",
        }

    except Exception:
        fallback = analyze_news_ai(items, symbol)

        if isinstance(fallback.get("summary"), dict):
            fallback = fallback["summary"]

        return fallback


def google_news_search(symbol, fund_name=None, limit=10):
    q = f"{symbol} KAP fon"
    if fund_name:
        q += f" {fund_name}"

    url = (
        "https://news.google.com/rss/search?"
        f"q={requests.utils.quote(q)}&hl=tr&gl=TR&ceid=TR:tr"
    )

    feed = feedparser.parse(url)

    rows = []
    for entry in feed.entries[:limit]:
        rows.append({
            "source": "Google News",
            "symbol": symbol,
            "title": entry.get("title", ""),
            "published": entry.get("published", ""),
            "link": entry.get("link", ""),
            "type": "Haber",
        })

    return rows


def mynet_kap_search(symbol, limit=20):
    url = "https://finans.mynet.com/borsa/kaphaberleri/"
    rows = []

    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
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

    except Exception:
        pass

    return rows


def kap_api_search(symbol, limit=20):
    rows = []
    url = "https://www.kap.org.tr/tr/api/disclosures"

    payloads = [
        {"keyword": symbol},
        {"searchText": symbol},
        {"fromDate": (dt.date.today() - dt.timedelta(days=30)).isoformat(),
         "toDate": dt.date.today().isoformat(),
         "keyword": symbol},
    ]

    for payload in payloads:
        try:
            r = requests.post(
                url,
                json=payload,
                timeout=12,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            if r.status_code != 200:
                continue

            data = r.json()
            if isinstance(data, dict):
                data = data.get("data") or data.get("items") or data.get("disclosures") or []

            for item in data[:limit]:
                title = (
                    item.get("title")
                    or item.get("disclosureType")
                    or item.get("subject")
                    or str(item)[:250]
                )

                rows.append({
                    "source": "KAP API",
                    "symbol": symbol,
                    "title": title,
                    "published": item.get("publishDate") or item.get("date") or "",
                    "link": "https://www.kap.org.tr",
                    "type": "KAP",
                })

            if rows:
                break

        except Exception:
            continue

    return rows


def get_symbol_news(symbol, fund_name=None):
    symbol = normalize_symbol(symbol)

    rows = []

    # Şimdilik hızlı ve çalışan kaynak
    rows.extend(google_news_search(symbol, fund_name=fund_name, limit=10))

    df = pd.DataFrame(rows)

    if df.empty:
        return df, analyze_news_ai([], symbol)

    df = df.drop_duplicates(subset=["title"]).reset_index(drop=True)
    analysis = analyze_news_with_llm(df.to_dict("records"), symbol)

    return df, analysis


def get_portfolio_news(portfolio_df):
    all_rows = []
    summaries = []

    if portfolio_df.empty:
        return pd.DataFrame(), []

    for _, row in portfolio_df.iterrows():
        symbol = normalize_symbol(row["kod_adi"])
        df, analysis = get_symbol_news(symbol)

        if not df.empty:
            all_rows.append(df)

        summaries.append(analysis)

    if all_rows:
        news_df = pd.concat(all_rows, ignore_index=True)
    else:
        news_df = pd.DataFrame()

    return news_df, summaries