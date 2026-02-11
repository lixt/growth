from app.db import SessionLocal
from app.services.ingest import upsert_trade_cal, upsert_daily
from app.crud import get_latest_open_date


def main():
    db = SessionLocal()
    try:
        upsert_trade_cal(db)
        latest = get_latest_open_date(db)
        if latest:
            upsert_daily(db, latest)
    finally:
        db.close()


if __name__ == "__main__":
    main()
