from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app import crud
from typing import Optional
from app.schemas import StockSuggest, BarPoint, TradeDate
from app.db import SessionLocal
from app.services.ingest import (
    upsert_stock_basic,
    upsert_trade_cal,
    upsert_daily,
    sync_minute_all,
)


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


@router.get("/stock/{ts_code}/intraday", response_model=list[BarPoint])
def intraday(ts_code: str, date: str, db: Session = Depends(get_session)):
    rows = crud.get_intraday(db, ts_code, date)
    return [
        BarPoint(
            ts_code=r.ts_code,
            time=r.trade_time,
            open=float(r.open) if r.open is not None else None,
            high=float(r.high) if r.high is not None else None,
            low=float(r.low) if r.low is not None else None,
            close=float(r.close) if r.close is not None else None,
            vol=float(r.vol) if r.vol is not None else None,
            amount=float(r.amount) if r.amount is not None else None,
        )
        for r in rows
    ]


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


def _run_sync(mode: str, date: Optional[str], rate_per_min: int, ts_code: Optional[str]):
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
        if mode == "minute":
            if ts_code:
                from app.services.ingest import upsert_minute

                upsert_minute(db, ts_code, target)
                return
            sync_minute_all(db, target, rate_per_min=rate_per_min)
            return
    finally:
        db.close()


@router.post("/admin/sync")
def manual_sync(
    background_tasks: BackgroundTasks,
    mode: str = Query("daily", pattern="^(basic|trade_cal|daily|minute)$"),
    date: Optional[str] = Query(default=None),
    rate_per_min: int = Query(default=480, ge=60, le=800),
    ts_code: Optional[str] = Query(default=None),
):
    background_tasks.add_task(_run_sync, mode, date, rate_per_min, ts_code)
    return {
        "status": "queued",
        "mode": mode,
        "date": date,
        "rate_per_min": rate_per_min,
        "ts_code": ts_code,
    }
