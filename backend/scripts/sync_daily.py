import sys
from datetime import datetime

from app.db import SessionLocal
from app.services.ingest import upsert_daily
from app.crud import get_latest_open_date


def main():
    target_date = None
    if len(sys.argv) > 1:
        target_date = sys.argv[1]

    db = SessionLocal()
    try:
        if not target_date:
            target_date = get_latest_open_date(db)
        if not target_date:
            raise SystemExit("trade calendar is empty, run bootstrap first")

        upsert_daily(db, target_date)
        print(f"daily synced: {target_date}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
