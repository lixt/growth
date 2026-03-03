import bisect
import math
from datetime import datetime, timedelta
from typing import Literal, Optional

from sqlalchemy import and_, case, desc, distinct, func, or_, select
from sqlalchemy.orm import Session

from app.constants import INDEX_BENCHMARKS
from app.models import Bar1D, DailyBasic1D, Index1D, StockBasic, SuspendD, TradeCal


def _to_float_or_none(v):
    if v is None:
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _pct_chg_or_none(cur, prev):
    cur_n = _to_float_or_none(cur)
    prev_n = _to_float_or_none(prev)
    if cur_n is None or prev_n is None or prev_n == 0:
        return None
    pct = ((cur_n - prev_n) / prev_n) * 100
    return pct if math.isfinite(pct) else None


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
    today_key = datetime.now().strftime("%Y%m%d")
    stmt = (
        select(TradeCal)
        .where(
            and_(
                TradeCal.exchange == "SSE",
                TradeCal.is_open == 1,
                TradeCal.cal_date <= today_key,
            )
        )
        .order_by(desc(TradeCal.cal_date))
        .limit(1)
    )
    row = db.execute(stmt).scalars().first()
    if not row:
        return None
    return row.cal_date


def get_calendar_status(
    db: Session,
    month: str,
    completion_ratio: float = 0.99,
):
    index_codes = [code for code, _ in INDEX_BENCHMARKS]
    index_expected_count = len(index_codes)
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
    Index1D.__table__.create(bind=db.get_bind(), checkfirst=True)

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

    index_stmt = (
        select(Index1D.trade_date, func.count(distinct(Index1D.ts_code)).label("index_daily_count"))
        .where(
            and_(
                Index1D.trade_date >= start_str,
                Index1D.trade_date <= end_str,
                Index1D.ts_code.in_(index_codes),
            )
        )
        .group_by(Index1D.trade_date)
    )
    index_map = {row[0]: int(row[1]) for row in db.execute(index_stmt).all()}

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
        index_daily_count = index_map.get(cal_date, 0)
        index_complete = index_daily_count >= index_expected_count if index_expected_count > 0 else True
        overlap_count = overlap_map.get(cal_date, 0)
        has_any_data = daily_stock_count > 0 or suspended_stock_count > 0 or index_daily_count > 0
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
        is_data_complete = bool(is_open) and daily_complete and index_complete

        if not is_open:
            action = "none"
        elif has_any_data:
            action = "clear"
        else:
            action = "pull"

        items.append(
            {
                "date": cal_date,
                "is_open": bool(is_open),
                "expected_stock_count": expected_stock_count,
                "index_expected_count": index_expected_count,
                "daily_stock_count": daily_stock_count,
                "index_daily_count": index_daily_count,
                "index_complete": index_complete,
                "suspended_stock_count": suspended_stock_count,
                "completed_stock_count": completed_stock_count,
                "unresolved_stock_count": unresolved_stock_count,
                "completion_rate": completion_rate,
                "has_any_data": has_any_data,
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


def get_index_snapshots(db: Session, date: str):
    Index1D.__table__.create(bind=db.get_bind(), checkfirst=True)
    index_codes = [code for code, _ in INDEX_BENCHMARKS]
    idx_stmt = select(Index1D).where(and_(Index1D.trade_date == date, Index1D.ts_code.in_(index_codes)))
    idx_rows = {row.ts_code: row for row in db.execute(idx_stmt).scalars().all()}

    items = []
    for code, name in INDEX_BENCHMARKS:
        row = idx_rows.get(code)
        items.append(
            {
                "ts_code": code,
                "name": name,
                "trade_date": date,
                "open": _to_float_or_none(row.open) if row else None,
                "high": _to_float_or_none(row.high) if row else None,
                "low": _to_float_or_none(row.low) if row else None,
                "close": _to_float_or_none(row.close) if row else None,
                "change": _to_float_or_none(row.change) if row else None,
                "pct_chg": _to_float_or_none(row.pct_chg) if row else None,
                "vol": _to_float_or_none(row.vol) if row else None,
                "amount": _to_float_or_none(row.amount) if row else None,
            }
        )
    return items


def get_market_overview(
    db: Session,
    date: str,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "amount",
    sort_order: Literal["asc", "desc"] = "desc",
    q: Optional[str] = None,
    market: Optional[str] = None,
    min_close: Optional[float] = None,
    max_close: Optional[float] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    min_vol: Optional[float] = None,
    max_vol: Optional[float] = None,
    min_total_mv: Optional[float] = None,
    max_total_mv: Optional[float] = None,
    min_circ_mv: Optional[float] = None,
    max_circ_mv: Optional[float] = None,
    min_turnover_rate: Optional[float] = None,
    max_turnover_rate: Optional[float] = None,
    min_pe: Optional[float] = None,
    max_pe: Optional[float] = None,
    min_pb: Optional[float] = None,
    max_pb: Optional[float] = None,
):
    indices = get_index_snapshots(db, date)
    DailyBasic1D.__table__.create(bind=db.get_bind(), checkfirst=True)
    prev_trade_subq = (
        select(
            Bar1D.ts_code.label("ts_code"),
            func.max(Bar1D.trade_date).label("prev_trade_date"),
        )
        .where(Bar1D.trade_date < date)
        .group_by(Bar1D.ts_code)
        .subquery()
    )
    prev_close_subq = (
        select(
            Bar1D.ts_code.label("ts_code"),
            Bar1D.close.label("prev_close"),
        )
        .join(
            prev_trade_subq,
            and_(
                Bar1D.ts_code == prev_trade_subq.c.ts_code,
                Bar1D.trade_date == prev_trade_subq.c.prev_trade_date,
            ),
        )
        .subquery()
    )
    pct_chg_expr = case(
        (
            and_(
                prev_close_subq.c.prev_close.is_not(None),
                prev_close_subq.c.prev_close != 0,
                Bar1D.close.is_not(None),
            ),
            ((Bar1D.close - prev_close_subq.c.prev_close) / prev_close_subq.c.prev_close) * 100,
        ),
        else_=None,
    ).label("pct_chg")

    stmt = (
        select(
            Bar1D.ts_code,
            StockBasic.name,
            StockBasic.symbol,
            StockBasic.market,
            StockBasic.list_date,
            Bar1D.open,
            Bar1D.high,
            Bar1D.low,
            Bar1D.close,
            prev_close_subq.c.prev_close,
            pct_chg_expr,
            Bar1D.vol,
            Bar1D.amount,
            DailyBasic1D.turnover_rate,
            DailyBasic1D.pe,
            DailyBasic1D.pb,
            DailyBasic1D.total_mv,
            DailyBasic1D.circ_mv,
        )
        .join(StockBasic, StockBasic.ts_code == Bar1D.ts_code, isouter=True)
        .join(
            DailyBasic1D,
            and_(DailyBasic1D.ts_code == Bar1D.ts_code, DailyBasic1D.trade_date == Bar1D.trade_date),
            isouter=True,
        )
        .join(prev_close_subq, prev_close_subq.c.ts_code == Bar1D.ts_code, isouter=True)
        .where(Bar1D.trade_date == date)
    )
    if q:
        qv = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Bar1D.ts_code.ilike(qv),
                StockBasic.name.ilike(qv),
                StockBasic.symbol.ilike(qv),
                StockBasic.cnspell.ilike(qv),
            )
        )
    if market:
        stmt = stmt.where(StockBasic.market == market)
    if min_close is not None:
        stmt = stmt.where(Bar1D.close >= min_close)
    if max_close is not None:
        stmt = stmt.where(Bar1D.close <= max_close)
    if min_amount is not None:
        stmt = stmt.where(Bar1D.amount >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(Bar1D.amount <= max_amount)
    if min_vol is not None:
        stmt = stmt.where(Bar1D.vol >= min_vol)
    if max_vol is not None:
        stmt = stmt.where(Bar1D.vol <= max_vol)
    if min_total_mv is not None:
        stmt = stmt.where(DailyBasic1D.total_mv >= min_total_mv)
    if max_total_mv is not None:
        stmt = stmt.where(DailyBasic1D.total_mv <= max_total_mv)
    if min_circ_mv is not None:
        stmt = stmt.where(DailyBasic1D.circ_mv >= min_circ_mv)
    if max_circ_mv is not None:
        stmt = stmt.where(DailyBasic1D.circ_mv <= max_circ_mv)
    if min_turnover_rate is not None:
        stmt = stmt.where(DailyBasic1D.turnover_rate >= min_turnover_rate)
    if max_turnover_rate is not None:
        stmt = stmt.where(DailyBasic1D.turnover_rate <= max_turnover_rate)
    if min_pe is not None:
        stmt = stmt.where(DailyBasic1D.pe >= min_pe)
    if max_pe is not None:
        stmt = stmt.where(DailyBasic1D.pe <= max_pe)
    if min_pb is not None:
        stmt = stmt.where(DailyBasic1D.pb >= min_pb)
    if max_pb is not None:
        stmt = stmt.where(DailyBasic1D.pb <= max_pb)

    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0)

    sort_map = {
        "ts_code": Bar1D.ts_code,
        "name": StockBasic.name,
        "market": StockBasic.market,
        "list_date": StockBasic.list_date,
        "open": Bar1D.open,
        "high": Bar1D.high,
        "low": Bar1D.low,
        "close": Bar1D.close,
        "pct_chg": pct_chg_expr,
        "vol": Bar1D.vol,
        "amount": Bar1D.amount,
        "turnover_rate": DailyBasic1D.turnover_rate,
        "pe": DailyBasic1D.pe,
        "pb": DailyBasic1D.pb,
        "total_mv": DailyBasic1D.total_mv,
        "circ_mv": DailyBasic1D.circ_mv,
    }
    sort_col = sort_map.get(sort_by, Bar1D.amount)
    sort_expr = sort_col.asc().nullslast() if sort_order == "asc" else sort_col.desc().nullslast()
    stmt = stmt.order_by(sort_expr, Bar1D.ts_code.asc()).offset(max(page - 1, 0) * page_size).limit(page_size)

    rows = db.execute(stmt).all()
    items = [
        {
            "ts_code": row[0],
            "name": row[1],
            "symbol": row[2],
            "market": row[3],
            "list_date": row[4],
            "open": _to_float_or_none(row[5]),
            "high": _to_float_or_none(row[6]),
            "low": _to_float_or_none(row[7]),
            "close": _to_float_or_none(row[8]),
            "pct_chg": _pct_chg_or_none(row[8], row[9]) if row[10] is None else _to_float_or_none(row[10]),
            "vol": _to_float_or_none(row[11]),
            "amount": _to_float_or_none(row[12]),
            "turnover_rate": _to_float_or_none(row[13]),
            "pe": _to_float_or_none(row[14]),
            "pb": _to_float_or_none(row[15]),
            "total_mv": _to_float_or_none(row[16]),
            "circ_mv": _to_float_or_none(row[17]),
        }
        for row in rows
    ]

    return {
        "date": date,
        "indices": indices,
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items,
    }
