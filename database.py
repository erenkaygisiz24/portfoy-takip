import sqlite3
from contextlib import contextmanager
from datetime import datetime
import pandas as pd

from config import DB_PATH


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS varliklar(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tur TEXT,
            kategori TEXT,
            kod_adi TEXT,
            adet REAL,
            maliyet REAL,
            hedef_fiyat REAL,
            ideal_oran REAL,
            islem_tarihi TEXT
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS market_cache(
            symbol TEXT,
            asset_type TEXT,
            price REAL,
            price_date TEXT,
            source TEXT,
            fetched_at TEXT,
            PRIMARY KEY(symbol, asset_type)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history_cache(
            symbol TEXT,
            asset_type TEXT,
            price REAL,
            price_date TEXT,
            source TEXT,
            fetched_at TEXT,
            PRIMARY KEY(symbol, asset_type, price_date)
        )
        """)


def normalize_symbol(symbol):
    return str(symbol or "").replace(".IS", "").strip().upper()


def portfolio_df():
    with db() as conn:
        df = pd.read_sql_query("SELECT * FROM varliklar ORDER BY id DESC", conn)
    if not df.empty:
        df["kod_adi"] = df["kod_adi"].map(normalize_symbol)
    return df


def add_asset(tur, kategori, kod_adi, adet, maliyet, hedef_fiyat, ideal_oran):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO varliklar(tur,kategori,kod_adi,adet,maliyet,hedef_fiyat,ideal_oran,islem_tarihi)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                tur, kategori, normalize_symbol(kod_adi), float(adet), float(maliyet),
                float(hedef_fiyat), float(ideal_oran), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ),
        )


def delete_asset(asset_id):
    with db() as conn:
        conn.execute("DELETE FROM varliklar WHERE id=?", (int(asset_id),))


def cache_price(symbol, asset_type, price, price_date, source):
    symbol = normalize_symbol(symbol)
    asset_type = str(asset_type)
    price_date = str(price_date or "-")
    with db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO market_cache
            VALUES (?,?,?,?,?,datetime('now'))
            """,
            (symbol, asset_type, float(price), price_date, source),
        )
        if price_date != "-":
            conn.execute(
                """
                INSERT OR REPLACE INTO price_history_cache
                VALUES (?,?,?,?,?,datetime('now'))
                """,
                (symbol, asset_type, float(price), price_date, source),
            )


def get_cached_price(symbol, asset_type):
    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM market_cache
            WHERE symbol=? AND asset_type=?
            """,
            (normalize_symbol(symbol), asset_type),
        ).fetchone()
    return dict(row) if row else None


def get_cache_table():
    with db() as conn:
        return pd.read_sql_query(
            """
            SELECT symbol, asset_type, price, price_date, source, fetched_at
            FROM market_cache
            ORDER BY fetched_at DESC
            """,
            conn,
        )
