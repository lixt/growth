import os
from datetime import datetime, timedelta
import requests
from typing import Optional
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="Growth", layout="wide")


def api_get(path: str, params=None):
    url = f"{API_BASE}{path}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=60)
def fetch_suggest(q: str):
    if not q.strip():
        return []
    return api_get("/api/search", {"q": q})


@st.cache_data(ttl=60)
def fetch_last_open():
    return api_get("/api/trade/last_open")


@st.cache_data(ttl=60)
def fetch_intraday(ts_code: str, date: str):
    return api_get(f"/api/stock/{ts_code}/intraday", {"date": date})


@st.cache_data(ttl=60)
def fetch_kline(ts_code: str, start: str, end: str):
    return api_get(f"/api/stock/{ts_code}/kline", {"start": start, "end": end})


st.title("Growth")

col1, col2 = st.columns([2, 1])

with col1:
    query = st.text_input("输入股票名 / 拼音 / 代码", key="query")

    suggestions = fetch_suggest(query) if query else []
    if suggestions:
        options = [f"{s.get('name','')} ({s.get('ts_code')})" for s in suggestions]
        selected_label = st.selectbox("选择股票", options=options, index=0)
        selected_index = options.index(selected_label)
        selected = suggestions[selected_index]
    else:
        selected = None

with col2:
    try:
        last_open = fetch_last_open().get("date")
    except Exception:
        last_open = None
    st.metric("最近交易日", last_open or "-")

if not selected:
    st.info("请先搜索并选择股票")
    st.stop()

ts_code = selected.get("ts_code")
name = selected.get("name") or ""

st.subheader(f"{name} {ts_code}")

# Date controls
if last_open:
    default_date = datetime.strptime(last_open, "%Y%m%d").date()
else:
    default_date = datetime.now().date()

intraday_date = st.date_input("分时日期", value=default_date, key="intraday_date")

kline_col1, kline_col2 = st.columns(2)
with kline_col1:
    kline_start = st.date_input("K线起始", value=default_date - timedelta(days=120), key="kline_start")
with kline_col2:
    kline_end = st.date_input("K线结束", value=default_date, key="kline_end")


def ymd(d):
    return d.strftime("%Y%m%d")


# Fetch data
with st.spinner("加载分时与K线数据..."):
    intraday = fetch_intraday(ts_code, ymd(intraday_date))
    kline = fetch_kline(ts_code, ymd(kline_start), ymd(kline_end))

intraday_df = pd.DataFrame(intraday)
kline_df = pd.DataFrame(kline)

# Intraday chart (line + volume)
if not intraday_df.empty:
    intraday_df["time"] = pd.to_datetime(intraday_df["time"])
    intraday_df = intraday_df.sort_values("time")

    fig_intraday = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.7, 0.3],
    )

    fig_intraday.add_trace(
        go.Scatter(
            x=intraday_df["time"],
            y=intraday_df["close"].fillna(intraday_df["open"]).fillna(0),
            mode="lines",
            name="价格",
            line=dict(color="#E6E6E6", width=1.2),
        ),
        row=1,
        col=1,
    )

    fig_intraday.add_trace(
        go.Bar(
            x=intraday_df["time"],
            y=intraday_df["vol"].fillna(0),
            name="成交量",
            marker_color="#2db55d",
        ),
        row=2,
        col=1,
    )

    fig_intraday.update_layout(
        height=420,
        template="plotly_dark",
        margin=dict(l=10, r=10, t=30, b=10),
        showlegend=False,
    )

    st.plotly_chart(fig_intraday, use_container_width=True)
else:
    st.warning("分时数据为空")

# Kline chart (candlestick + volume)
if not kline_df.empty:
    kline_df["time"] = pd.to_datetime(kline_df["time"], format="%Y%m%d")
    kline_df = kline_df.sort_values("time")

    fig_k = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.7, 0.3],
    )

    fig_k.add_trace(
        go.Candlestick(
            x=kline_df["time"],
            open=kline_df["open"],
            high=kline_df["high"],
            low=kline_df["low"],
            close=kline_df["close"],
            name="K线",
            increasing_line_color="#e84545",
            decreasing_line_color="#2db55d",
        ),
        row=1,
        col=1,
    )

    fig_k.add_trace(
        go.Bar(
            x=kline_df["time"],
            y=kline_df["vol"].fillna(0),
            name="成交量",
            marker_color="#3c7",
        ),
        row=2,
        col=1,
    )

    fig_k.update_layout(
        height=480,
        template="plotly_dark",
        margin=dict(l=10, r=10, t=30, b=10),
        showlegend=False,
    )

    st.plotly_chart(fig_k, use_container_width=True)
else:
    st.warning("K线数据为空")
