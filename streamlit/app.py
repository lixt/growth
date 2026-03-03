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


@st.cache_data(ttl=20)
def fetch_market_overview(
    trade_date: str,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    q: str = "",
    market: str = "",
    min_close: Optional[float] = None,
    max_close: Optional[float] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    min_vol: Optional[float] = None,
    max_vol: Optional[float] = None,
    min_total_mv: Optional[float] = None,
    max_total_mv: Optional[float] = None,
    min_turnover_rate: Optional[float] = None,
    max_turnover_rate: Optional[float] = None,
    min_pe: Optional[float] = None,
    max_pe: Optional[float] = None,
    min_pb: Optional[float] = None,
    max_pb: Optional[float] = None,
):
    params: dict[str, Any] = {
        "date": trade_date,
        "page": page,
        "page_size": page_size,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    if q.strip():
        params["q"] = q.strip()
    if market:
        params["market"] = market
    for key, value in {
        "min_close": min_close,
        "max_close": max_close,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "min_vol": min_vol,
        "max_vol": max_vol,
        "min_total_mv": min_total_mv,
        "max_total_mv": max_total_mv,
        "min_turnover_rate": min_turnover_rate,
        "max_turnover_rate": max_turnover_rate,
        "min_pe": min_pe,
        "max_pe": max_pe,
        "min_pb": min_pb,
        "max_pb": max_pb,
    }.items():
        if value is not None:
            params[key] = value
    return api_get("/api/market/overview", params)


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


def maybe_float(v: str) -> Optional[float]:
    txt = (v or "").strip()
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def yi_to_amount_raw(v: Optional[float]) -> Optional[float]:
    return None if v is None else v * 100000


def yi_to_mv_raw(v: Optional[float]) -> Optional[float]:
    return None if v is None else v * 10000


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


def render_market_page():
    st.title("行情展示")
    try:
        last_open = fetch_last_open().get("date")
    except Exception:
        last_open = None

    default_date = datetime.strptime(last_open, "%Y%m%d").date() if last_open else datetime.now().date()
    if "market_date" not in st.session_state:
        st.session_state["market_date"] = default_date
    elif st.session_state["market_date"] > default_date:
        st.session_state["market_date"] = default_date
    if "market_page" not in st.session_state:
        st.session_state["market_page"] = 1
    if "market_filters" not in st.session_state:
        st.session_state["market_filters"] = {
            "q": "",
            "market": "",
            "sort_by": "amount",
            "sort_order": "desc",
            "page_size": "50",
            "min_close": "",
            "max_close": "",
            "min_amount": "",
            "max_amount": "",
            "min_vol": "",
            "max_vol": "",
            "min_total_mv": "",
            "max_total_mv": "",
            "min_turnover_rate": "",
            "max_turnover_rate": "",
            "min_pe": "",
            "max_pe": "",
            "min_pb": "",
            "max_pb": "",
        }

    nav1, nav2, nav3, nav4 = st.columns([1, 2, 1, 1])
    if nav1.button("◀ 前一天", use_container_width=True):
        st.session_state["market_date"] = st.session_state["market_date"] - timedelta(days=1)
        st.session_state["market_page"] = 1
        st.rerun()

    picker = nav2.date_input("交易日", value=st.session_state["market_date"], key="market_date_picker")
    if picker != st.session_state["market_date"]:
        st.session_state["market_date"] = picker
        st.session_state["market_page"] = 1

    if nav3.button("后一天 ▶", use_container_width=True):
        st.session_state["market_date"] = st.session_state["market_date"] + timedelta(days=1)
        st.session_state["market_page"] = 1
        st.rerun()

    if nav4.button("最近交易日", use_container_width=True):
        st.session_state["market_date"] = default_date
        st.session_state["market_page"] = 1
        st.rerun()

    f = st.session_state["market_filters"]
    with st.form("market_filter_form"):
        st.caption("筛选与排序")
        f_q, f_market, f_sort, f_order, f_page_size = st.columns([2, 1, 1, 1, 1])
        q = f_q.text_input("代码/名称/拼音", value=f["q"])
        market = f_market.selectbox(
            "板块",
            options=["", "主板", "创业板", "科创板", "北交所"],
            index=["", "主板", "创业板", "科创板", "北交所"].index(f["market"]) if f["market"] in {"", "主板", "创业板", "科创板", "北交所"} else 0,
            format_func=lambda x: "全部" if x == "" else x,
        )
        sort_by = f_sort.selectbox(
            "排序列",
            options=["amount", "vol", "close", "total_mv", "turnover_rate", "pe", "pb", "ts_code", "name"],
            index=["amount", "vol", "close", "total_mv", "turnover_rate", "pe", "pb", "ts_code", "name"].index(f["sort_by"]) if f["sort_by"] in {"amount", "vol", "close", "total_mv", "turnover_rate", "pe", "pb", "ts_code", "name"} else 0,
        )
        sort_order = f_order.selectbox("方向", options=["desc", "asc"], index=0 if f["sort_order"] == "desc" else 1)
        page_size = f_page_size.selectbox("每页", options=["30", "50", "100"], index=["30", "50", "100"].index(f["page_size"]) if f["page_size"] in {"30", "50", "100"} else 1)

        a1, a2, a3, a4 = st.columns(4)
        min_close = a1.text_input("收盘价 ≥", value=f["min_close"])
        max_close = a2.text_input("收盘价 ≤", value=f["max_close"])
        min_amount = a3.text_input("成交额(亿元) ≥", value=f["min_amount"])
        max_amount = a4.text_input("成交额(亿元) ≤", value=f["max_amount"])

        b1, b2, b3, b4 = st.columns(4)
        min_vol = b1.text_input("成交量 ≥", value=f["min_vol"])
        max_vol = b2.text_input("成交量 ≤", value=f["max_vol"])
        min_total_mv = b3.text_input("总市值(亿元) ≥", value=f["min_total_mv"])
        max_total_mv = b4.text_input("总市值(亿元) ≤", value=f["max_total_mv"])

        c1, c2, c3, c4 = st.columns(4)
        min_turnover_rate = c1.text_input("换手率(%) ≥", value=f["min_turnover_rate"])
        max_turnover_rate = c2.text_input("换手率(%) ≤", value=f["max_turnover_rate"])
        min_pe = c3.text_input("PE ≥", value=f["min_pe"])
        max_pe = c4.text_input("PE ≤", value=f["max_pe"])

        d1, d2, _, _ = st.columns(4)
        min_pb = d1.text_input("PB ≥", value=f["min_pb"])
        max_pb = d2.text_input("PB ≤", value=f["max_pb"])

        op1, op2 = st.columns(2)
        apply_clicked = op1.form_submit_button("应用筛选", use_container_width=True)
        reset_clicked = op2.form_submit_button("重置筛选", use_container_width=True)

    if apply_clicked:
        st.session_state["market_filters"] = {
            "q": q,
            "market": market,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page_size": page_size,
            "min_close": min_close,
            "max_close": max_close,
            "min_amount": min_amount,
            "max_amount": max_amount,
            "min_vol": min_vol,
            "max_vol": max_vol,
            "min_total_mv": min_total_mv,
            "max_total_mv": max_total_mv,
            "min_turnover_rate": min_turnover_rate,
            "max_turnover_rate": max_turnover_rate,
            "min_pe": min_pe,
            "max_pe": max_pe,
            "min_pb": min_pb,
            "max_pb": max_pb,
        }
        st.session_state["market_page"] = 1
        st.rerun()

    if reset_clicked:
        st.session_state["market_filters"] = {
            "q": "",
            "market": "",
            "sort_by": "amount",
            "sort_order": "desc",
            "page_size": "50",
            "min_close": "",
            "max_close": "",
            "min_amount": "",
            "max_amount": "",
            "min_vol": "",
            "max_vol": "",
            "min_total_mv": "",
            "max_total_mv": "",
            "min_turnover_rate": "",
            "max_turnover_rate": "",
            "min_pe": "",
            "max_pe": "",
            "min_pb": "",
            "max_pb": "",
        }
        st.session_state["market_page"] = 1
        st.rerun()

    f = st.session_state["market_filters"]
    trade_date = ymd(st.session_state["market_date"])
    page = int(st.session_state["market_page"])
    page_size_num = int(f["page_size"])

    data = fetch_market_overview(
        trade_date=trade_date,
        page=page,
        page_size=page_size_num,
        sort_by=f["sort_by"],
        sort_order=f["sort_order"],
        q=f["q"],
        market=f["market"],
        min_close=maybe_float(f["min_close"]),
        max_close=maybe_float(f["max_close"]),
        min_amount=yi_to_amount_raw(maybe_float(f["min_amount"])),
        max_amount=yi_to_amount_raw(maybe_float(f["max_amount"])),
        min_vol=maybe_float(f["min_vol"]),
        max_vol=maybe_float(f["max_vol"]),
        min_total_mv=yi_to_mv_raw(maybe_float(f["min_total_mv"])),
        max_total_mv=yi_to_mv_raw(maybe_float(f["max_total_mv"])),
        min_turnover_rate=maybe_float(f["min_turnover_rate"]),
        max_turnover_rate=maybe_float(f["max_turnover_rate"]),
        min_pe=maybe_float(f["min_pe"]),
        max_pe=maybe_float(f["max_pe"]),
        min_pb=maybe_float(f["min_pb"]),
        max_pb=maybe_float(f["max_pb"]),
    )

    st.subheader(f"指数概览（{trade_date}）")
    indices = data.get("indices", [])
    if indices:
        cols = st.columns(len(indices))
        for i, idx in enumerate(indices):
            close = idx.get("close")
            pct = idx.get("pct_chg")
            close_txt = "-" if close is None else f"{float(close):,.2f}"
            pct_txt = "-" if pct is None else f"{float(pct):.2f}%"
            cols[i].metric(idx.get("name", idx.get("ts_code", "-")), close_txt, pct_txt)
    else:
        st.info("该日期暂无指数数据。")

    st.subheader("股票列表")
    total = int(data.get("total") or 0)
    items = data.get("items", [])
    st.caption(f"共 {total} 条，第 {page} 页")

    if items:
        df = pd.DataFrame(items)
        df["最新"] = pd.to_numeric(df.get("close"), errors="coerce")
        df["当日涨跌幅(%)"] = pd.to_numeric(df.get("pct_chg"), errors="coerce")
        df["成交额(亿元)"] = (pd.to_numeric(df.get("amount"), errors="coerce") / 100000).round(2)
        df["总市值(亿元)"] = (pd.to_numeric(df.get("total_mv"), errors="coerce") / 10000).round(0)
        df["换手率(%)"] = pd.to_numeric(df.get("turnover_rate"), errors="coerce")
        df["PE"] = pd.to_numeric(df.get("pe"), errors="coerce")
        df["PB"] = pd.to_numeric(df.get("pb"), errors="coerce")
        df = df.rename(
            columns={
                "ts_code": "代码",
                "name": "名称",
                "market": "板块",
            }
        )
        show_cols = ["代码", "名称", "板块", "最新", "当日涨跌幅(%)", "成交额(亿元)", "总市值(亿元)", "换手率(%)", "PE", "PB"]
        df = df[[c for c in show_cols if c in df.columns]]
        st.dataframe(df, use_container_width=True, height=620)
    else:
        st.info("该日期暂无已拉取股票数据。")

    total_pages = max(1, (total + page_size_num - 1) // page_size_num)
    p1, p2, p3, p4, p5 = st.columns([1, 1, 2, 1, 1])
    if p1.button("首页", disabled=page <= 1, use_container_width=True):
        st.session_state["market_page"] = 1
        st.rerun()
    if p2.button("上一页", disabled=page <= 1, use_container_width=True):
        st.session_state["market_page"] = max(1, page - 1)
        st.rerun()
    p3.markdown(f"<div style='text-align:center;padding-top:8px'>第 {page} / {total_pages} 页</div>", unsafe_allow_html=True)
    if p4.button("下一页", disabled=page >= total_pages, use_container_width=True):
        st.session_state["market_page"] = min(total_pages, page + 1)
        st.rerun()
    if p5.button("末页", disabled=page >= total_pages, use_container_width=True):
        st.session_state["market_page"] = total_pages
        st.rerun()


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

    selected_key = st.session_state.get("selected_pull_date")
    if selected_key not in day_map:
        auto_date = None
        if last_open and last_open in day_map:
            auto_date = last_open
        else:
            today_key = ymd(date.today())
            open_dates = sorted([d["date"] for d in days if d.get("is_open") and d["date"] <= today_key])
            auto_date = open_dates[-1] if open_dates else sorted([d["date"] for d in days])[-1]
        st.session_state["selected_pull_date"] = auto_date

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

        m1, m2, m3 = st.columns(3)
        m1.metric("是否交易日", "是" if row["is_open"] else "否")
        m2.metric("日线覆盖", f"{row['daily_stock_count']} / {row['expected_stock_count']}")
        m3.metric("指数覆盖", f"{row.get('index_daily_count', 0)} / {row.get('index_expected_count', 5)}")

        if row["is_open"]:
            action_label = "重新拉取数据（覆盖写）" if row["action"] == "clear" else "拉取数据"
            if st.button(action_label, type="primary", key=f"sync_{selected_date}"):
                with st.spinner("提交全市场拉取任务..."):
                    result = trigger_full_day_sync(selected_date)
                fetch_calendar_status.clear()
                fetch_sync_tasks.clear()
                fetch_market_overview.clear()
                task_id = result.get("task_id")
                st.success(f"已提交 {selected_date} 的全量拉取任务。任务ID: {task_id}")
                st.info("任务在后端异步执行，完成后点击“刷新状态”查看最新覆盖情况。")
        else:
            st.info("该日期为休市日，不支持拉取。")


with st.sidebar:
    st.title("Growth")
    page = st.radio("导航", ["行情展示", "数据拉取"], key="sidebar_nav")
    st.caption("左侧保留可扩展导航，右侧为功能展示区。")

if page == "行情展示":
    render_market_page()
else:
    render_data_pull_page()
