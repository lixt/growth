from collections import deque
from datetime import datetime, timedelta
import time
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from typing import Optional
from app.models import StockBasic, TradeCal, Bar1D, Bar1M
from app.providers.tushare_provider import TushareProvider


provider = TushareProvider()


def upsert_stock_basic(db: Session):
    df = provider.stock_basic()
    if df is None or df.empty:
        return 0

    rows = df.to_dict(orient="records")
    stmt = insert(StockBasic).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[StockBasic.ts_code],
        set_={
            "symbol": stmt.excluded.symbol,
            "name": stmt.excluded.name,
            "cnspell": stmt.excluded.cnspell,
            "market": stmt.excluded.market,
            "list_date": stmt.excluded.list_date,
        },
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def upsert_trade_cal(db: Session, start_date: Optional[str] = None, end_date: Optional[str] = None):
    df = provider.trade_cal(start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return 0

    rows = df.to_dict(orient="records")
    stmt = insert(TradeCal).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[TradeCal.exchange, TradeCal.cal_date],
        set_={
            "is_open": stmt.excluded.is_open,
            "pretrade_date": stmt.excluded.pretrade_date,
        },
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def upsert_daily(db: Session, trade_date: str):
    df = provider.daily(trade_date)
    if df is None or df.empty:
        return 0

    rows = df.to_dict(orient="records")
    for row in rows:
        row.pop("pre_close", None)
        row.pop("change", None)
        row.pop("pct_chg", None)

    stmt = insert(Bar1D).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Bar1D.ts_code, Bar1D.trade_date],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "vol": stmt.excluded.vol,
            "amount": stmt.excluded.amount,
        },
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def upsert_minute(db: Session, ts_code: str, trade_date: str):
    df = provider.pro_bar_1m(ts_code, trade_date)
    if df is None or df.empty:
        return 0

    if "trade_time" not in df.columns and "trade_date" in df.columns:
        df["trade_time"] = df["trade_date"].apply(lambda x: datetime.strptime(str(x), "%Y%m%d%H%M%S"))
    elif "trade_time" in df.columns:
        df["trade_time"] = df["trade_time"].apply(
            lambda x: x if isinstance(x, datetime) else datetime.strptime(str(x), "%Y-%m-%d %H:%M:%S")
        )

    rows = df[["ts_code", "trade_time", "open", "high", "low", "close", "vol", "amount"]].to_dict(orient="records")
    stmt = insert(Bar1M).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Bar1M.ts_code, Bar1M.trade_time],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "vol": stmt.excluded.vol,
            "amount": stmt.excluded.amount,
        },
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def cleanup_old_minute(db: Session, keep_days: int = 365):
    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    db.query(Bar1M).filter(Bar1M.trade_time < cutoff).delete(synchronize_session=False)
    db.commit()


def sync_minute_all(db: Session, trade_date: str, rate_per_min: int = 480):
    codes = [row.ts_code for row in db.query(StockBasic.ts_code).all()]
    window = deque()

    for idx, ts_code in enumerate(codes, start=1):
        while len(window) >= rate_per_min:
            now = time.time()
            if now - window[0] >= 60:
                window.popleft()
            else:
                time.sleep(0.2)

        upsert_minute(db, ts_code, trade_date)
        window.append(time.time())

        if idx % 200 == 0:
            time.sleep(0.5)
