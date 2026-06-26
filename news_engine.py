import datetime as dt
import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup

from database import normalize_symbol


def simple_ai_summary(items, symbol):
    if not items:
        return f"{symbol} için son dönemde anlamlı haber/KAP bulunamadı."

    titles = " ".join([str(x.get("title", "")) for x in items[:8]]).lower()

    risk_words = ["dava", "ceza", "zarar", "iptal", "uyarı", "denetim", "düşüş"]
    positive_words = ["kar", "kâr", "büyüme", "anlaşma", "yatırım", "artış", "temettü"]

    risk = sum(w in titles for w in risk_words)
    positive = sum(w in titles for w in positive_words)

    if risk > positive:
        tone = "negatif/risk odaklı"
    elif positive > risk:
        tone = "pozitif"
    else:
        tone = "nötr"

    top = items[0].get("title", "")
    return (
        f"{symbol} için bulunan haber/KAP akışı genel olarak {tone} görünüyor. "
        f"Öne çıkan başlık: {top}"
    )


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
    rows.extend(kap_api_search(symbol))
    rows.extend(mynet_kap_search(symbol))
    rows.extend(google_news_search(symbol, fund_name=fund_name))

    df = pd.DataFrame(rows)

    if df.empty:
        return df, simple_ai_summary([], symbol)

    df = df.drop_duplicates(subset=["title"]).reset_index(drop=True)
    summary = simple_ai_summary(df.to_dict("records"), symbol)

    return df, summary


def get_portfolio_news(portfolio_df):
    all_rows = []
    summaries = []

    if portfolio_df.empty:
        return pd.DataFrame(), []

    for _, row in portfolio_df.iterrows():
        symbol = normalize_symbol(row["kod_adi"])
        df, summary = get_symbol_news(symbol)

        if not df.empty:
            all_rows.append(df)

        summaries.append({
            "symbol": symbol,
            "summary": summary,
        })

    if all_rows:
        news_df = pd.concat(all_rows, ignore_index=True)
    else:
        news_df = pd.DataFrame()

    return news_df, summaries