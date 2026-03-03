from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, distinct, func
from sqlalchemy.orm import Session

from app.constants import INDEX_BENCHMARKS
from app.db import get_session
from app import crud
from typing import Optional
from app.schemas import (
    StockSuggest,
    BarPoint,
    TradeDate,
    CalendarStatusResponse,
    CalendarDayStatus,
    MarketOverviewResponse,
    UnresolvedStockItem,
    UnresolvedStocksResponse,
    IndexSnapshotResponse,
)
from app.db import SessionLocal
from app.services.ingest import (
    upsert_stock_basic,
    upsert_trade_cal,
    upsert_daily,
    upsert_daily_basic,
    upsert_index_daily,
    replace_daily,
    replace_daily_basic,
    replace_index_daily,
    upsert_suspend_d,
    clear_day_data,
)
from app.models import Bar1D, Index1D, StockBasic, SuspendD
from app.services.task_tracker import task_tracker


router = APIRouter()


@router.get("/search", response_model=list[StockSuggest])
def search(q: str = Query("", min_length=1), db: Session = Depends(get_session)):
    results = crud.search_stocks(db, q, limit=10)
    return [
        StockSuggest(
            ts_code=r.ts_code,
            name=r.name,
            symbol=r.symbol,
            cnspell=r.cnspell,
        )
        for r in results
    ]


@router.get("/trade/last_open", response_model=TradeDate)
def last_open(db: Session = Depends(get_session)):
    date = crud.get_latest_open_date(db)
    if not date:
        raise HTTPException(status_code=404, detail="trade calendar not initialized")
    return TradeDate(date=date)


@router.get("/data/calendar", response_model=CalendarStatusResponse)
def data_calendar(
    month: Optional[str] = Query(default=None, pattern=r"^\d{6}$"),
    db: Session = Depends(get_session),
):
    target_month = month
    if not target_month:
        latest = crud.get_latest_open_date(db)
        if not latest:
            raise HTTPException(status_code=404, detail="trade calendar not initialized")
        target_month = latest[:6]

    days = crud.get_calendar_status(db, month=target_month)
    return CalendarStatusResponse(month=target_month, days=[CalendarDayStatus(**d) for d in days])


@router.get("/stock/{ts_code}/kline", response_model=list[BarPoint])
def kline(ts_code: str, start: str, end: str, db: Session = Depends(get_session)):
    rows = crud.get_kline(db, ts_code, start, end)
    return [
        BarPoint(
            ts_code=r.ts_code,
            time=r.trade_date,
            open=float(r.open) if r.open is not None else None,
            high=float(r.high) if r.high is not None else None,
            low=float(r.low) if r.low is not None else None,
            close=float(r.close) if r.close is not None else None,
            vol=float(r.vol) if r.vol is not None else None,
            amount=float(r.amount) if r.amount is not None else None,
        )
        for r in rows
    ]


@router.get("/data/day_unresolved", response_model=UnresolvedStocksResponse)
def day_unresolved(
    date: str = Query(..., pattern=r"^\d{8}$"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_session),
):
    items = crud.get_unresolved_stocks(db, date=date, limit=limit)
    return UnresolvedStocksResponse(date=date, items=[UnresolvedStockItem(**i) for i in items])


@router.get("/data/index_snapshot", response_model=IndexSnapshotResponse)
def index_snapshot(
    date: str = Query(..., pattern=r"^\d{8}$"),
    db: Session = Depends(get_session),
):
    indices = crud.get_index_snapshots(db, date=date)
    return IndexSnapshotResponse(date=date, indices=indices)


@router.get("/market/overview", response_model=MarketOverviewResponse)
def market_overview(
    date: str = Query(..., pattern=r"^\d{8}$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
    sort_by: str = Query(default="amount"),
    sort_order: str = Query(default="desc", pattern=r"^(asc|desc)$"),
    q: Optional[str] = Query(default=None),
    market: Optional[str] = Query(default=None),
    min_close: Optional[float] = Query(default=None),
    max_close: Optional[float] = Query(default=None),
    min_amount: Optional[float] = Query(default=None),
    max_amount: Optional[float] = Query(default=None),
    min_vol: Optional[float] = Query(default=None),
    max_vol: Optional[float] = Query(default=None),
    min_total_mv: Optional[float] = Query(default=None),
    max_total_mv: Optional[float] = Query(default=None),
    min_circ_mv: Optional[float] = Query(default=None),
    max_circ_mv: Optional[float] = Query(default=None),
    min_turnover_rate: Optional[float] = Query(default=None),
    max_turnover_rate: Optional[float] = Query(default=None),
    min_pe: Optional[float] = Query(default=None),
    max_pe: Optional[float] = Query(default=None),
    min_pb: Optional[float] = Query(default=None),
    max_pb: Optional[float] = Query(default=None),
    db: Session = Depends(get_session),
):
    data = crud.get_market_overview(
        db,
        date=date,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        q=q,
        market=market,
        min_close=min_close,
        max_close=max_close,
        min_amount=min_amount,
        max_amount=max_amount,
        min_vol=min_vol,
        max_vol=max_vol,
        min_total_mv=min_total_mv,
        max_total_mv=max_total_mv,
        min_circ_mv=min_circ_mv,
        max_circ_mv=max_circ_mv,
        min_turnover_rate=min_turnover_rate,
        max_turnover_rate=max_turnover_rate,
        min_pe=min_pe,
        max_pe=max_pe,
        min_pb=min_pb,
        max_pb=max_pb,
    )
    return MarketOverviewResponse(**data)


def _run_sync(mode: str, date: Optional[str]):
    db = SessionLocal()
    try:
        if mode == "basic":
            upsert_stock_basic(db)
            return
        if mode == "trade_cal":
            upsert_trade_cal(db)
            return

        target = date or crud.get_latest_open_date(db)
        if not target:
            return

        if mode == "index":
            upsert_index_daily(db, target)
            return

        if mode == "daily":
            upsert_daily(db, target)
            upsert_daily_basic(db, target)
            return
    finally:
        db.close()


def _run_full_day_sync(task_id: str, date: str, overwrite: bool):
    task_tracker.start_task(task_id)
    db = SessionLocal()
    try:
        index_codes = [code for code, _ in INDEX_BENCHMARKS]
        index_total = len(index_codes)
        task_tracker.set_step(task_id, "index", "指数拉取", total=index_total)
        if overwrite:
            replace_index_daily(db, date)
        else:
            upsert_index_daily(db, date)
        index_done = (
            db.query(func.count(distinct(Index1D.ts_code)))
            .filter(and_(Index1D.trade_date == date, Index1D.ts_code.in_(index_codes)))
            .scalar()
            or 0
        )
        task_tracker.finish_step(task_id, "index", done=min(index_done, index_total))
        task_tracker.update_step(task_id, "index", message=f"指数覆盖: {index_done}/{index_total}")

        expected_codes = [
            row[0]
            for row in db.query(StockBasic.ts_code)
            .filter(and_(StockBasic.list_date.is_not(None), StockBasic.list_date != "", StockBasic.list_date <= date))
            .all()
        ]
        expected_set = set(expected_codes)
        daily_total = len(expected_set)
        task_tracker.set_step(task_id, "daily", "日线拉取", total=daily_total)
        if overwrite:
            daily_done = replace_daily(db, date)
            replace_daily_basic(db, date)
        else:
            daily_done = upsert_daily(db, date)
            upsert_daily_basic(db, date)
        task_tracker.finish_step(task_id, "daily", done=min(daily_done, daily_total) if daily_total > 0 else daily_done)

        daily_codes = {row[0] for row in db.query(distinct(Bar1D.ts_code)).filter(Bar1D.trade_date == date).all()}
        missing_codes = sorted(expected_set - daily_codes)

        task_tracker.set_step(task_id, "suspend", "停牌信息同步", total=1)
        suspend_done = upsert_suspend_d(db, date, focus_ts_codes=missing_codes)
        task_tracker.finish_step(task_id, "suspend", done=1)

        suspended_count = (
            db.query(func.count(distinct(SuspendD.ts_code)))
            .filter(SuspendD.trade_date == date)
            .scalar()
            or 0
        )
        overlap_count = (
            db.query(func.count(distinct(SuspendD.ts_code)))
            .join(
                Bar1D,
                and_(Bar1D.trade_date == SuspendD.trade_date, Bar1D.ts_code == SuspendD.ts_code),
            )
            .filter(SuspendD.trade_date == date)
            .scalar()
            or 0
        )
        completed = min(daily_total, len(daily_codes) + max(suspended_count - overlap_count, 0))
        unresolved = max(daily_total - completed, 0)
        task_tracker.update_step(
            task_id,
            "suspend",
            message=f"停牌记录: {suspend_done}，缺失待确认: {unresolved}",
        )
        task_tracker.finish_task(task_id)
    except Exception as exc:
        task_tracker.update_step(task_id, "daily", status="failed", message=str(exc))
        task_tracker.fail_task(task_id, str(exc))
        raise
    finally:
        db.close()


@router.post("/admin/sync")
def manual_sync(
    background_tasks: BackgroundTasks,
    mode: str = Query("daily", pattern="^(basic|trade_cal|daily|index)$"),
    date: Optional[str] = Query(default=None),
):
    background_tasks.add_task(_run_sync, mode, date)
    return {
        "status": "queued",
        "mode": mode,
        "date": date,
    }


@router.post("/admin/sync/full_day")
def manual_sync_full_day(
    background_tasks: BackgroundTasks,
    date: str = Query(..., pattern=r"^\d{8}$"),
    overwrite: bool = Query(default=True),
):
    task = task_tracker.create_task(
        mode="full_day",
        date=date,
        payload={"overwrite": overwrite},
    )
    background_tasks.add_task(_run_full_day_sync, task["id"], date, overwrite)
    return {
        "status": "queued",
        "mode": "full_day",
        "task_id": task["id"],
        "date": date,
        "overwrite": overwrite,
    }


@router.post("/admin/clear/day")
def manual_clear_day(
    date: str = Query(..., pattern=r"^\d{8}$"),
    db: Session = Depends(get_session),
):
    deleted = clear_day_data(db, date)
    return {
        "status": "cleared",
        "date": date,
        **deleted,
    }


@router.get("/admin/tasks")
def admin_tasks(
    limit: int = Query(default=20, ge=1, le=200),
    status: Optional[str] = Query(default=None, pattern=r"^(queued|running|success|failed)$"),
):
    items = task_tracker.list_tasks(limit=limit, status=status)
    return {"items": items}


@router.get("/admin/tasks/{task_id}")
def admin_task_detail(task_id: str):
    item = task_tracker.get_task(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="task not found")
    return item
