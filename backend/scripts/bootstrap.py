from datetime import datetime, timedelta

from app.db import SessionLocal
from app.services.ingest import upsert_stock_basic, upsert_trade_cal


def main():
    db = SessionLocal()
    try:
        upsert_stock_basic(db)

        start_date = (datetime.utcnow() - timedelta(days=730)).strftime("%Y%m%d")
        end_date = datetime.utcnow().strftime("%Y%m%d")
        upsert_trade_cal(db, start_date=start_date, end_date=end_date)
    finally:
        db.close()


if __name__ == "__main__":
    main()
