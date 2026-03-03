from typing import Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.constants import INDEX_BENCHMARKS
from app.models import StockBasic, TradeCal, Bar1D, Index1D, DailyBasic1D, SuspendD
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


def upsert_daily_basic(db: Session, trade_date: str):
    DailyBasic1D.__table__.create(bind=db.get_bind(), checkfirst=True)
    df = provider.daily_basic(trade_date)
    if df is None or df.empty:
        return 0

    rows = df.to_dict(orient="records")
    stmt = insert(DailyBasic1D).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DailyBasic1D.ts_code, DailyBasic1D.trade_date],
        set_={
            "turnover_rate": stmt.excluded.turnover_rate,
            "pe": stmt.excluded.pe,
            "pb": stmt.excluded.pb,
            "total_mv": stmt.excluded.total_mv,
            "circ_mv": stmt.excluded.circ_mv,
        },
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def replace_daily(db: Session, trade_date: str):
    db.query(Bar1D).filter(Bar1D.trade_date == trade_date).delete(synchronize_session=False)
    db.commit()
    return upsert_daily(db, trade_date)


def replace_daily_basic(db: Session, trade_date: str):
    DailyBasic1D.__table__.create(bind=db.get_bind(), checkfirst=True)
    db.query(DailyBasic1D).filter(DailyBasic1D.trade_date == trade_date).delete(synchronize_session=False)
    db.commit()
    return upsert_daily_basic(db, trade_date)


def upsert_index_daily(db: Session, trade_date: str):
    Index1D.__table__.create(bind=db.get_bind(), checkfirst=True)

    rows_map: dict[tuple[str, str], dict] = {}
    required_codes = [code for code, _ in INDEX_BENCHMARKS]
    required_set = set(required_codes)

    def _merge(df):
        if df is None or df.empty:
            return
        for row in df.to_dict(orient="records"):
            ts_code = row.get("ts_code")
            td = row.get("trade_date")
            if not ts_code or not td or ts_code not in required_set:
                continue
            rows_map[(ts_code, td)] = {
                "ts_code": ts_code,
                "trade_date": td,
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "pre_close": row.get("pre_close"),
                "change": row.get("change"),
                "pct_chg": row.get("pct_chg"),
                "vol": row.get("vol"),
                "amount": row.get("amount"),
            }

    # Tushare 在部分账号策略下 index_daily 必须提供 ts_code，这里逐个指数兜底拉取。
    for code in required_codes:
        try:
            _merge(provider.index_daily(trade_date=trade_date, ts_code=code))
        except Exception:
            continue

    if not rows_map:
        return 0

    rows = list(rows_map.values())
    stmt = insert(Index1D).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Index1D.ts_code, Index1D.trade_date],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "pre_close": stmt.excluded.pre_close,
            "change": stmt.excluded.change,
            "pct_chg": stmt.excluded.pct_chg,
            "vol": stmt.excluded.vol,
            "amount": stmt.excluded.amount,
        },
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def replace_index_daily(db: Session, trade_date: str):
    Index1D.__table__.create(bind=db.get_bind(), checkfirst=True)
    db.query(Index1D).filter(Index1D.trade_date == trade_date).delete(synchronize_session=False)
    db.commit()
    return upsert_index_daily(db, trade_date)


def clear_day_data(db: Session, trade_date: str):
    Index1D.__table__.create(bind=db.get_bind(), checkfirst=True)
    DailyBasic1D.__table__.create(bind=db.get_bind(), checkfirst=True)
    SuspendD.__table__.create(bind=db.get_bind(), checkfirst=True)
    daily_deleted = db.query(Bar1D).filter(Bar1D.trade_date == trade_date).delete(synchronize_session=False)
    daily_basic_deleted = (
        db.query(DailyBasic1D).filter(DailyBasic1D.trade_date == trade_date).delete(synchronize_session=False)
    )
    index_deleted = db.query(Index1D).filter(Index1D.trade_date == trade_date).delete(synchronize_session=False)
    suspend_deleted = db.query(SuspendD).filter(SuspendD.trade_date == trade_date).delete(synchronize_session=False)
    db.commit()
    return {
        "daily_deleted": int(daily_deleted or 0),
        "daily_basic_deleted": int(daily_basic_deleted or 0),
        "index_deleted": int(index_deleted or 0),
        "suspend_deleted": int(suspend_deleted or 0),
    }


def _normalize_suspend_rows(df):
    if df is None or df.empty:
        return []
    keep = [c for c in ["trade_date", "ts_code", "suspend_timing", "suspend_type"] if c in df.columns]
    rows = df[keep].to_dict(orient="records")
    # 仅保留停牌记录；有些账号或参数会返回复牌记录
    return [r for r in rows if str(r.get("suspend_type") or "").upper() in {"", "S"}]


def _chunk_codes(codes: list[str], size: int = 200):
    for i in range(0, len(codes), size):
        yield codes[i : i + size]


def upsert_suspend_d(db: Session, trade_date: str, focus_ts_codes: Optional[list[str]] = None):
    SuspendD.__table__.create(bind=db.get_bind(), checkfirst=True)

    # 先拉取当日全部停复牌，再统一筛选停牌(S)，和官网调试口径一致
    rows = _normalize_suspend_rows(provider.suspend_d(trade_date=trade_date, suspend_type=None))
    dedup = {(r.get("trade_date"), r.get("ts_code")): r for r in rows if r.get("trade_date") and r.get("ts_code")}

    # 若按交易日返回为空或明显偏少，对缺失股票做分批兜底查询
    if focus_ts_codes:
        for batch in _chunk_codes(sorted(set(focus_ts_codes))):
            df = provider.suspend_d(
                ts_code=",".join(batch),
                start_date=trade_date,
                end_date=trade_date,
                suspend_type=None,
            )
            for row in _normalize_suspend_rows(df):
                key = (row.get("trade_date"), row.get("ts_code"))
                if key[0] and key[1]:
                    dedup[key] = row

    db.query(SuspendD).filter(SuspendD.trade_date == trade_date).delete(synchronize_session=False)
    db.commit()

    if not dedup:
        return 0

    rows = list(dedup.values())
    stmt = insert(SuspendD).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[SuspendD.trade_date, SuspendD.ts_code],
        set_={
            "suspend_timing": stmt.excluded.suspend_timing,
            "suspend_type": stmt.excluded.suspend_type,
        },
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
