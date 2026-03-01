from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, distinct, func
from sqlalchemy.orm import Session

from app.db import get_session
from app import crud
from typing import Optional
from app.schemas import (
    StockSuggest,
    BarPoint,
    TradeDate,
    CalendarStatusResponse,
    CalendarDayStatus,
    UnresolvedStockItem,
    UnresolvedStocksResponse,
)
from app.db import SessionLocal
from app.services.ingest import (
    upsert_stock_basic,
    upsert_trade_cal,
    upsert_daily,
    replace_daily,
    upsert_suspend_d,
    clear_day_data,
)
from app.models import Bar1D, StockBasic, SuspendD
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

        if mode == "daily":
            upsert_daily(db, target)
            return
    finally:
        db.close()


def _run_full_day_sync(task_id: str, date: str, overwrite: bool):
    task_tracker.start_task(task_id)
    db = SessionLocal()
    try:
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
        else:
            daily_done = upsert_daily(db, date)
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
    mode: str = Query("daily", pattern="^(basic|trade_cal|daily)$"),
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
