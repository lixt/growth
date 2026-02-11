from datetime import datetime
from typing import Optional
from sqlalchemy import select, or_, desc, and_
from sqlalchemy.orm import Session

from app.models import StockBasic, Bar1M, Bar1D, TradeCal


def search_stocks(db: Session, q: str, limit: int = 10):
    q = q.strip()
    if not q:
        return []

    stmt = (
        select(StockBasic)
        .where(
            or_(
                StockBasic.ts_code.ilike(f"%{q}%"),
                StockBasic.symbol.ilike(f"%{q}%"),
                StockBasic.name.ilike(f"%{q}%"),
                StockBasic.cnspell.ilike(f"%{q}%"),
            )
        )
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def get_intraday(db: Session, ts_code: str, date_str: str):
    start = datetime.strptime(date_str, "%Y%m%d")
    end = datetime.strptime(date_str + "235959", "%Y%m%d%H%M%S")

    stmt = (
        select(Bar1M)
        .where(and_(Bar1M.ts_code == ts_code, Bar1M.trade_time >= start, Bar1M.trade_time <= end))
        .order_by(Bar1M.trade_time.asc())
    )
    return db.execute(stmt).scalars().all()


def get_kline(db: Session, ts_code: str, start: str, end: str):
    stmt = (
        select(Bar1D)
        .where(and_(Bar1D.ts_code == ts_code, Bar1D.trade_date >= start, Bar1D.trade_date <= end))
        .order_by(Bar1D.trade_date.asc())
    )
    return db.execute(stmt).scalars().all()


def get_latest_open_date(db: Session) -> Optional[str]:
    stmt = select(TradeCal).where(TradeCal.is_open == 1).order_by(desc(TradeCal.cal_date)).limit(1)
    row = db.execute(stmt).scalars().first()
    if not row:
        return None
    return row.cal_date
