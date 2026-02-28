# Growth MVP

A minimal end-to-end stack for stock data ingestion (Tushare Pro), storage (PostgreSQL), API (FastAPI), and UI (React + ECharts).

## Prerequisites
- Python 3.10+
- Node 18+
- Docker (optional for local Postgres)

## Quick Start
1. Start Postgres (local dev)

```bash
docker compose up -d
```

2. Configure environment

```bash
cp .env.example .env
# Fill in your Tushare token
```

3. Create DB tables

```bash
cd backend
python -m scripts.init_db
```

4. Bootstrap base data

```bash
python -m scripts.bootstrap
```

5. Sync daily data (latest open day)

```bash
python -m scripts.sync_daily
```

6. Sync minute data (latest open day) — full market, heavy

```bash
python -m scripts.sync_minute
```

7. Run API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Streamlit Frontend (Recommended)

```bash
cd streamlit
pip install -r requirements.txt
streamlit run app.py
```

If you want to use the backend venv:

```bash
cd backend
.venv/bin/pip install -r ../streamlit/requirements.txt
.venv/bin/streamlit run ../streamlit/app.py
```

## One-command Dev

```bash
./dev.sh
```

## Legacy React Frontend (Optional)

```bash
cd frontend
npm install
npm run dev
```

## API endpoints
- `GET /api/search?q=`
- `GET /api/trade/last_open`
- `GET /api/stock/{ts_code}/intraday?date=YYYYMMDD`
- `GET /api/stock/{ts_code}/kline?start=YYYYMMDD&end=YYYYMMDD`
- `POST /api/admin/sync?mode=basic|trade_cal|daily|minute&date=YYYYMMDD&rate_per_min=480&ts_code=000001.SZ`

## Notes
- Minute data is large. Default retention is 12 months (rolling cleanup in `scripts.sync_minute`).
- For production, consider OSS/Parquet archive for historical minutes, or a columnar DB.
