import calendar
import os
from datetime import date, datetime, timedelta
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="Growth", layout="wide", initial_sidebar_state="expanded")


def api_get(path: str, params: Optional[dict[str, Any]] = None):
    url = f"{API_BASE}{path}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, params: Optional[dict[str, Any]] = None):
    url = f"{API_BASE}{path}"
    resp = requests.post(url, params=params, timeout=30)
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
def fetch_kline(ts_code: str, start: str, end: str):
    return api_get(f"/api/stock/{ts_code}/kline", {"start": start, "end": end})


@st.cache_data(ttl=60)
def fetch_calendar_status(month: str):
    return api_get("/api/data/calendar", {"month": month})


@st.cache_data(ttl=2)
def fetch_sync_tasks(limit: int = 20):
    return api_get("/api/admin/tasks", {"limit": limit})


def trigger_full_day_sync(trade_date: str):
    return api_post(
        "/api/admin/sync/full_day",
        {"date": trade_date, "overwrite": "true"},
    )


def render_task_board():
    task_data = fetch_sync_tasks(20)
    items = task_data.get("items", [])

    queued_count = len([t for t in items if t.get("status") == "queued"])
    running_count = len([t for t in items if t.get("status") == "running"])
    success_count = len([t for t in items if t.get("status") == "success"])
    failed_count = len([t for t in items if t.get("status") == "failed"])

    st.subheader("任务看板")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("排队中", queued_count)
    c2.metric("执行中", running_count)
    c3.metric("成功", success_count)
    c4.metric("失败", failed_count)
    if queued_count > 0 or running_count > 0:
        st.caption("检测到任务执行中，页面每5秒自动刷新。")
        if hasattr(st, "autorefresh"):
            st.autorefresh(interval=5000, key="task_board_refresh")

    if not items:
        st.caption("暂无拉取任务")
        return

    for task in items:
        header = (
            f"任务 {task.get('id')} | {task.get('date')} | {task.get('status')} "
            f"| 总进度 {task.get('progress', {}).get('done', 0)}/{task.get('progress', {}).get('total', 0)}"
        )
        with st.expander(header, expanded=task.get("status") in {"queued", "running"}):
            overall_percent = float(task.get("progress", {}).get("percent", 0.0)) / 100.0
            st.progress(min(max(overall_percent, 0.0), 1.0))
            st.caption(
                f"创建: {task.get('created_at')} | 开始: {task.get('started_at') or '-'} | "
                f"结束: {task.get('finished_at') or '-'}"
            )
            if task.get("error"):
                st.error(task.get("error"))

            steps = list(task.get("steps", {}).values())
            st.write(f"子任务数: {task.get('task_count', len(steps))}")
            for step in steps:
                st.write(
                    f"{step.get('name')} | {step.get('status')} | "
                    f"{step.get('done', 0)}/{step.get('total', 0)}"
                )
                step_percent = float(step.get("percent", 0.0)) / 100.0
                st.progress(min(max(step_percent, 0.0), 1.0))
                if step.get("message"):
                    st.caption(f"最近处理: {step.get('message')}")


def ymd(d: date):
    return d.strftime("%Y%m%d")


def render_kline_chart(kline: list[dict[str, Any]]):
    kline_df = pd.DataFrame(kline)
    if kline_df.empty:
        st.warning("K线数据为空")
        return

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


def render_test_page():
    st.title("测试功能")

    col1, col2 = st.columns([2, 1])

    with col1:
        query = st.text_input("输入股票名 / 拼音 / 代码", key="query")
        suggestions = fetch_suggest(query) if query else []
        if suggestions:
            options = [f"{s.get('name', '')} ({s.get('ts_code')})" for s in suggestions]
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
        return

    ts_code = selected.get("ts_code")
    name = selected.get("name") or ""
    st.subheader(f"{name} {ts_code}")

    if last_open:
        default_date = datetime.strptime(last_open, "%Y%m%d").date()
    else:
        default_date = datetime.now().date()

    kline_col1, kline_col2 = st.columns(2)
    with kline_col1:
        kline_start = st.date_input("K线起始", value=default_date - timedelta(days=120), key="kline_start")
    with kline_col2:
        kline_end = st.date_input("K线结束", value=default_date, key="kline_end")

    with st.spinner("加载K线数据..."):
        kline = fetch_kline(ts_code, ymd(kline_start), ymd(kline_end))

    render_kline_chart(kline)


def render_data_pull_page():
    st.title("数据拉取")

    try:
        last_open = fetch_last_open().get("date")
    except Exception:
        last_open = None

    if last_open:
        default_month = datetime.strptime(last_open, "%Y%m%d").date().replace(day=1)
    else:
        default_month = date.today().replace(day=1)

    top_col1, top_col2 = st.columns([2, 1])
    with top_col1:
        month_date = st.date_input("选择月份", value=default_month, key="pull_month")
        month_key = month_date.strftime("%Y%m")
    with top_col2:
        st.write("")
        st.write("")
        if st.button("刷新状态", use_container_width=True):
            fetch_calendar_status.clear()
            fetch_sync_tasks.clear()
            st.rerun()

    render_task_board()
    st.divider()

    data = fetch_calendar_status(month_key)
    days = data.get("days", [])
    day_map = {d["date"]: d for d in days}

    if not days:
        st.warning("该月份没有交易日历数据，请先执行交易日历同步。")
        return

    st.caption("状态说明：✅ 数据完整  ⚠️ 数据不完整  ⛔ 休市")

    year = int(month_key[:4])
    month = int(month_key[4:6])
    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    header_cols = st.columns(7)
    for i, text in enumerate(week_days):
        header_cols[i].markdown(f"**{text}**")

    cal = calendar.Calendar(firstweekday=0)
    for week in cal.monthdayscalendar(year, month):
        cols = st.columns(7)
        for idx, day in enumerate(week):
            if day == 0:
                cols[idx].write("")
                continue

            day_key = f"{year}{month:02d}{day:02d}"
            row = day_map.get(day_key)
            if not row:
                cols[idx].button(f"{day}", key=f"day_{day_key}", use_container_width=True, disabled=True)
                continue

            if not row["is_open"]:
                icon = "⛔"
            elif row["is_data_complete"]:
                icon = "✅"
            else:
                icon = "⚠️"

            hint = f"日线 {row['daily_stock_count']}/{row['expected_stock_count']}"
            clicked = cols[idx].button(
                f"{day} {icon}",
                key=f"day_{day_key}",
                use_container_width=True,
                disabled=not row["is_open"],
                help=hint,
            )
            if clicked:
                st.session_state["selected_pull_date"] = day_key

    selected_date = st.session_state.get("selected_pull_date")
    if selected_date and selected_date in day_map:
        row = day_map[selected_date]
        st.divider()
        st.subheader(f"日期 {selected_date}")

        m1, m2 = st.columns(2)
        m1.metric("是否交易日", "是" if row["is_open"] else "否")
        m2.metric("日线覆盖", f"{row['daily_stock_count']} / {row['expected_stock_count']}")

        if row["is_open"]:
            action_label = "重新拉取数据（覆盖写）" if row["action"] == "repull" else "拉取数据"
            if st.button(action_label, type="primary", key=f"sync_{selected_date}"):
                with st.spinner("提交全市场拉取任务..."):
                    result = trigger_full_day_sync(selected_date)
                fetch_calendar_status.clear()
                fetch_sync_tasks.clear()
                task_id = result.get("task_id")
                st.success(f"已提交 {selected_date} 的全量拉取任务。任务ID: {task_id}")
                st.info("任务在后端异步执行，完成后点击“刷新状态”查看最新覆盖情况。")
        else:
            st.info("该日期为休市日，不支持拉取。")


with st.sidebar:
    st.title("Growth")
    page = st.radio("导航", ["测试功能", "数据拉取"], key="sidebar_nav")
    st.caption("左侧保留可扩展导航，右侧为功能展示区。")

if page == "测试功能":
    render_test_page()
else:
    render_data_pull_page()
