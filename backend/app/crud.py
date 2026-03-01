import bisect
import math
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, or_, desc, and_, func, distinct
from sqlalchemy.orm import Session

from app.models import StockBasic, Bar1D, TradeCal, SuspendD


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


def get_calendar_status(
    db: Session,
    month: str,
    completion_ratio: float = 0.99,
):
    month_start = datetime.strptime(month + "01", "%Y%m%d")
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    start_str = month_start.strftime("%Y%m%d")
    end_str = (month_end - timedelta(days=1)).strftime("%Y%m%d")

    cal_stmt = (
        select(TradeCal.cal_date, TradeCal.is_open)
        .where(
            and_(
                TradeCal.exchange == "SSE",
                TradeCal.cal_date >= start_str,
                TradeCal.cal_date <= end_str,
            )
        )
        .order_by(TradeCal.cal_date.asc())
    )
    cal_rows = db.execute(cal_stmt).all()

    daily_stmt = (
        select(Bar1D.trade_date, func.count(distinct(Bar1D.ts_code)).label("daily_stock_count"))
        .where(and_(Bar1D.trade_date >= start_str, Bar1D.trade_date <= end_str))
        .group_by(Bar1D.trade_date)
    )
    daily_map = {row[0]: int(row[1]) for row in db.execute(daily_stmt).all()}

    SuspendD.__table__.create(bind=db.get_bind(), checkfirst=True)

    suspend_stmt = (
        select(SuspendD.trade_date, func.count(distinct(SuspendD.ts_code)).label("suspended_stock_count"))
        .where(and_(SuspendD.trade_date >= start_str, SuspendD.trade_date <= end_str))
        .group_by(SuspendD.trade_date)
    )
    suspend_map = {row[0]: int(row[1]) for row in db.execute(suspend_stmt).all()}

    overlap_stmt = (
        select(SuspendD.trade_date, func.count(distinct(SuspendD.ts_code)).label("overlap_count"))
        .join(
            Bar1D,
            and_(Bar1D.trade_date == SuspendD.trade_date, Bar1D.ts_code == SuspendD.ts_code),
        )
        .where(and_(SuspendD.trade_date >= start_str, SuspendD.trade_date <= end_str))
        .group_by(SuspendD.trade_date)
    )
    overlap_map = {row[0]: int(row[1]) for row in db.execute(overlap_stmt).all()}

    list_dates_stmt = (
        select(StockBasic.list_date)
        .where(
            and_(
                StockBasic.list_date.is_not(None),
                StockBasic.list_date != "",
                StockBasic.list_date <= end_str,
            )
        )
        .order_by(StockBasic.list_date.asc())
    )
    list_dates = [row[0] for row in db.execute(list_dates_stmt).all()]

    items = []
    for cal_date, is_open in cal_rows:
        expected_stock_count = bisect.bisect_right(list_dates, cal_date)
        daily_stock_count = daily_map.get(cal_date, 0)
        suspended_stock_count = suspend_map.get(cal_date, 0)
        overlap_count = overlap_map.get(cal_date, 0)
        has_any_data = daily_stock_count > 0 or suspended_stock_count > 0
        completed_stock_count = min(
            expected_stock_count,
            daily_stock_count + max(suspended_stock_count - overlap_count, 0),
        )
        unresolved_stock_count = max(expected_stock_count - completed_stock_count, 0) if has_any_data else 0
        daily_threshold = max(1, math.ceil(expected_stock_count * completion_ratio)) if expected_stock_count > 0 else 0
        daily_complete = completed_stock_count >= daily_threshold if daily_threshold > 0 else False
        completion_rate = (
            round((completed_stock_count / expected_stock_count) * 100, 2) if expected_stock_count > 0 else 0.0
        )
        is_data_complete = bool(is_open) and daily_complete

        if not is_open:
            action = "none"
        elif completed_stock_count > 0:
            action = "clear"
        else:
            action = "pull"

        items.append(
            {
                "date": cal_date,
                "is_open": bool(is_open),
                "expected_stock_count": expected_stock_count,
                "daily_stock_count": daily_stock_count,
                "suspended_stock_count": suspended_stock_count,
                "completed_stock_count": completed_stock_count,
                "unresolved_stock_count": unresolved_stock_count,
                "completion_rate": completion_rate,
                "is_data_complete": is_data_complete,
                "action": action,
            }
        )

    return items


def get_unresolved_stocks(db: Session, date: str, limit: int = 200):
    daily_exists = (
        select(Bar1D.ts_code)
        .where(and_(Bar1D.trade_date == date, Bar1D.ts_code == StockBasic.ts_code))
        .limit(1)
    )
    suspend_exists = (
        select(SuspendD.ts_code)
        .where(and_(SuspendD.trade_date == date, SuspendD.ts_code == StockBasic.ts_code))
        .limit(1)
    )
    stmt = (
        select(StockBasic.ts_code, StockBasic.name)
        .where(
            and_(
                StockBasic.list_date.is_not(None),
                StockBasic.list_date != "",
                StockBasic.list_date <= date,
                ~daily_exists.exists(),
                ~suspend_exists.exists(),
            )
        )
        .order_by(StockBasic.ts_code.asc())
        .limit(limit)
    )
    return [{"ts_code": row[0], "name": row[1]} for row in db.execute(stmt).all()]
