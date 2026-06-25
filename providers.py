import datetime as dt
import time
from dataclasses import dataclass

import pandas as pd
import requests
import yfinance as yf

from config import HEADERS, TEFAS_URL, YF_ALIASES, GRAM_ALTIN_ALIASES
from database import normalize_symbol, cache_price, get_cached_price


@dataclass
class PriceResult:
    symbol: str
    asset_type: str
    price: float | None
    price_date: str | None
    source: str
    status: str


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
    except Exception:
        return None


def classify_asset_type(tur):
    text = str(tur or "").strip()
    low = text.lower()
    if text == "Fon":
        return "Fon"
    if "hisse" in low:
        return "Hisse Senedi"
    if "döviz" in low or "doviz" in low:
        return "Döviz"
    if "emtia" in low or "altın" in low or "altin" in low:
        return "Emtia"
    return text or "Diğer"


def yf_symbol(symbol, asset_type):
    symbol = normalize_symbol(symbol)
    if symbol in YF_ALIASES:
        return YF_ALIASES[symbol]
    if asset_type == "Hisse Senedi":
        return f"{symbol}.IS"
    return symbol


def retry_call(func, tries=3, wait=0.7):
    last = None
    for _ in range(tries):
        try:
            return func()
        except Exception as exc:
            last = exc
            time.sleep(wait)
    raise last


class CacheProvider:
    name = "SQLite cache"

    def get_price(self, symbol, asset_type):
        symbol = normalize_symbol(symbol)
        cached = get_cached_price(symbol, asset_type)
        if not cached:
            return PriceResult(symbol, asset_type, None, None, self.name, "cache_miss")
        return PriceResult(
            symbol=symbol,
            asset_type=asset_type,
            price=float(cached["price"]),
            price_date=cached["price_date"],
            source=self.name,
            status="cache_fallback",
        )


class YahooProvider:
    name = "Yahoo Finance"

    def fetch_many(self, symbol_map, lookback_days=15):
        """
        symbol_map: {original_symbol: (yf_symbol, asset_type)}
        """
        rows = []
        if not symbol_map:
            return pd.DataFrame()

        tickers = sorted({v[0] for v in symbol_map.values()})
        try:
            raw = yf.download(
                tickers,
                period=f"{int(lookback_days)}d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=True,
                group_by="ticker",
            )
        except Exception:
            raw = pd.DataFrame()

        for original, (ticker, asset_type) in symbol_map.items():
            price = None
            price_date = None

            try:
                if raw.empty:
                    raise ValueError("empty batch")

                if len(tickers) == 1:
                    close = raw["Close"]
                elif isinstance(raw.columns, pd.MultiIndex):
                    close = raw[ticker]["Close"]
                else:
                    close = raw["Close"]

                close = close.dropna()
                if close.empty:
                    raise ValueError("empty close")

                price = float(close.iloc[-1])
                price_date = pd.Timestamp(close.index[-1]).strftime("%Y-%m-%d")

            except Exception:
                single = self.get_price(original, asset_type, lookback_days=lookback_days)
                if single.price is not None:
                    rows.append(single.__dict__)
                continue

            cache_price(original, asset_type, price, price_date, self.name)
            rows.append(
                PriceResult(original, asset_type, price, price_date, self.name, "live_or_last_close").__dict__
            )

        return pd.DataFrame(rows)

    def get_price(self, symbol, asset_type, lookback_days=15):
        symbol = normalize_symbol(symbol)
        ticker = yf_symbol(symbol, asset_type)

        try:
            df = yf.download(
                ticker,
                period=f"{int(lookback_days)}d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )

            if df.empty:
                return PriceResult(symbol, asset_type, None, None, self.name, "empty_response")

            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]

            close = close.dropna()
            if close.empty:
                return PriceResult(symbol, asset_type, None, None, self.name, "empty_close")

            price = float(close.iloc[-1])
            price_date = pd.Timestamp(close.index[-1]).strftime("%Y-%m-%d")
            cache_price(symbol, asset_type, price, price_date, self.name)

            return PriceResult(symbol, asset_type, price, price_date, self.name, "live_or_last_close")

        except Exception as exc:
            return PriceResult(symbol, asset_type, None, None, self.name, f"error: {exc}")


class TefasProvider:
    name = "TEFAS official endpoint"

    def _fetch_date(self, date_obj):
        date_text = date_obj.strftime("%d.%m.%Y")

        def request_once():
            response = requests.post(
                TEFAS_URL,
                headers=HEADERS,
                data={"fontip": "YAT", "bastarih": date_text, "bittarih": date_text},
                timeout=12,
            )
            response.raise_for_status()
            return response

        try:
            response = retry_call(request_once, tries=2, wait=0.4)
            df = pd.DataFrame(response.json())

            if df.empty or "FONKODU" not in df.columns or "FIYAT" not in df.columns:
                return pd.DataFrame()

            df["symbol"] = df["FONKODU"].map(normalize_symbol)
            df["price"] = df["FIYAT"].map(parse_float)
            df["price_date"] = date_obj.isoformat()

            return df.dropna(subset=["symbol", "price"])[["symbol", "price", "price_date"]]
        except Exception:
            return pd.DataFrame()

    def get_many(self, symbols, lookback_days=15):
        symbols = tuple(sorted({normalize_symbol(s) for s in symbols if normalize_symbol(s)}))
        rows = []
        found = set()
        today = dt.date.today()

        for i in range(int(lookback_days)):
            day = today - dt.timedelta(days=i)
            df = self._fetch_date(day)
            if df.empty:
                continue

            df = df[df["symbol"].isin(symbols)]
            if df.empty:
                continue

            for _, row in df.iterrows():
                sym = row["symbol"]
                if sym in found:
                    continue

                price = float(row["price"])
                price_date = row["price_date"]
                cache_price(sym, "Fon", price, price_date, self.name)
                rows.append(
                    PriceResult(sym, "Fon", price, price_date, self.name, "live_or_last_close").__dict__
                )
                found.add(sym)

            if len(found) == len(symbols):
                break

        return pd.DataFrame(rows)

    def get_price(self, symbol, asset_type="Fon", lookback_days=15):
        df = self.get_many((symbol,), lookback_days=lookback_days)
        if df.empty:
            return PriceResult(normalize_symbol(symbol), "Fon", None, None, self.name, "not_found")
        row = df.iloc[0]
        return PriceResult(row["symbol"], "Fon", float(row["price"]), row["price_date"], row["source"], row["status"])


class DerivedProvider:
    name = "Derived market data"

    def __init__(self):
        self.yahoo = YahooProvider()

    def get_gram_altin(self):
        usd = self.yahoo.get_price("USD", "Döviz")
        ons = self.yahoo.get_price("ONS", "Emtia")

        if usd.price is None or ons.price is None:
            return None

        gram = usd.price * ons.price / 31.1034768
        price_date = max(str(usd.price_date), str(ons.price_date))

        for alias in GRAM_ALTIN_ALIASES:
            cache_price(alias, "Emtia", gram, price_date, self.name)

        return PriceResult("GRAM ALTIN", "Emtia", gram, price_date, self.name, "derived_last_close")


class ProviderManager:
    def __init__(self):
        self.tefas = TefasProvider()
        self.yahoo = YahooProvider()
        self.cache = CacheProvider()
        self.derived = DerivedProvider()

    def get_price(self, symbol, asset_type, cost_fallback=None):
        symbol = normalize_symbol(symbol)
        asset_type = classify_asset_type(asset_type)

        if asset_type == "Fon":
            result = self.tefas.get_price(symbol, "Fon")
            if result.price is not None:
                return result

            cached = self.cache.get_price(symbol, "Fon")
            if cached.price is not None:
                return cached

        elif asset_type in {"Hisse Senedi", "Döviz"}:
            result = self.yahoo.get_price(symbol, asset_type)
            if result.price is not None:
                return result

            cached = self.cache.get_price(symbol, asset_type)
            if cached.price is not None:
                return cached

        elif asset_type == "Emtia":
            if symbol in GRAM_ALTIN_ALIASES:
                result = self.derived.get_gram_altin()
                if result and result.price is not None:
                    result.symbol = symbol
                    return result

            result = self.yahoo.get_price(symbol, asset_type)
            if result.price is not None:
                return result

            cached = self.cache.get_price(symbol, asset_type)
            if cached.price is not None:
                return cached

        if cost_fallback is not None:
            return PriceResult(symbol, asset_type, float(cost_fallback), "-", "Maliyet fallback", "cost_fallback")

        return PriceResult(symbol, asset_type, None, None, "No source", "failed")

    def get_prices_for_portfolio(self, portfolio_df):
        if portfolio_df.empty:
            return pd.DataFrame()

        df = portfolio_df.copy()
        df["symbol"] = df["kod_adi"].map(normalize_symbol)
        df["asset_type"] = df["tur"].map(classify_asset_type)

        rows = []

        # Batch TEFAS
        fon_symbols = tuple(df.loc[df["asset_type"] == "Fon", "symbol"].unique())
        fon_found = set()
        if fon_symbols:
            fon_df = self.tefas.get_many(fon_symbols)
            if not fon_df.empty:
                rows.extend(fon_df.to_dict("records"))
                fon_found = set(fon_df["symbol"].tolist())

        # Batch Yahoo
        yf_df = df[df["asset_type"].isin(["Hisse Senedi", "Döviz"])].drop_duplicates(["symbol", "asset_type"])
        symbol_map = {
            r["symbol"]: (yf_symbol(r["symbol"], r["asset_type"]), r["asset_type"])
            for _, r in yf_df.iterrows()
        }
        y_prices = self.yahoo.fetch_many(symbol_map)
        y_found = set()
        if not y_prices.empty:
            rows.extend(y_prices.to_dict("records"))
            y_found = set(y_prices["symbol"].tolist())

        # Emtia + missing fallback
        for _, row in df.drop_duplicates(["symbol", "asset_type"]).iterrows():
            sym = row["symbol"]
            typ = row["asset_type"]

            if typ == "Fon" and sym in fon_found:
                continue
            if typ in {"Hisse Senedi", "Döviz"} and sym in y_found:
                continue

            result = self.get_price(sym, typ, cost_fallback=row.get("maliyet", None))
            rows.append(result.__dict__)

        out = pd.DataFrame(rows)
        if out.empty:
            return out

        out["symbol"] = out["symbol"].map(normalize_symbol)
        return out.drop_duplicates(["symbol", "asset_type"], keep="last")
