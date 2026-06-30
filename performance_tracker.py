import pandas as pd
from database import db


def init_performance_db():
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_snapshots(
                snapshot_date TEXT PRIMARY KEY,
                total_cost REAL,
                total_value REAL,
                pnl REAL,
                pnl_pct REAL
            )
            """
        )


def save_daily_snapshot(total_cost, total_value, pnl, pnl_pct):
    init_performance_db()
    with db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO portfolio_snapshots
            VALUES (date('now'), ?, ?, ?, ?)
            """,
            (float(total_cost), float(total_value), float(pnl), float(pnl_pct)),
        )


def load_snapshots():
    init_performance_db()
    with db() as conn:
        df = pd.read_sql_query(
            """
            SELECT snapshot_date, total_cost, total_value, pnl, pnl_pct
            FROM portfolio_snapshots
            ORDER BY snapshot_date
            """,
            conn,
        )
    if not df.empty:
        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    return df
