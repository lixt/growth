import { useEffect, useMemo, useState, type CSSProperties } from "react";

import "./styles.css";
import type { CalendarDayStatus, IndexSnapshot, MarketStockItem } from "./api";
import {
  clearDayData,
  getAdminTasks,
  getCalendarStatus,
  getLastOpen,
  getMarketOverview,
  getUnresolvedStocks,
  triggerFullDaySync
} from "./api";

function ymd(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}${m}${day}`;
}

function parseDayKey(v: string) {
  const y = Number(v.slice(0, 4));
  const m = Number(v.slice(4, 6));
  const d = Number(v.slice(6, 8));
  return new Date(y, m - 1, d);
}

function shiftDayKey(dayKey: string, delta: number) {
  const d = parseDayKey(dayKey);
  d.setDate(d.getDate() + delta);
  return ymd(d);
}

function toDateInput(dayKey: string) {
  return `${dayKey.slice(0, 4)}-${dayKey.slice(4, 6)}-${dayKey.slice(6, 8)}`;
}

function fromDateInput(v: string) {
  return v.replaceAll("-", "");
}

function monthKeyOf(d: Date) {
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function parseMonthKey(month: string) {
  return {
    year: Number(month.slice(0, 4)),
    month: Number(month.slice(4, 6))
  };
}

function buildMonthKey(year: number, month: number) {
  return `${year}${String(month).padStart(2, "0")}`;
}

function shiftMonth(monthKey: string, delta: number) {
  const { year, month } = parseMonthKey(monthKey);
  const d = new Date(year, month - 1 + delta, 1);
  return monthKeyOf(d);
}

function formatMonthLabel(monthKey: string) {
  const { year, month } = parseMonthKey(monthKey);
  return `${year}年${String(month).padStart(2, "0")}月`;
}

function buildCalendarCells(month: string) {
  const year = Number(month.slice(0, 4));
  const mon = Number(month.slice(4, 6));
  const first = new Date(year, mon - 1, 1);
  const days = new Date(year, mon, 0).getDate();
  const startWeekday = (first.getDay() + 6) % 7;
  const cells: (string | null)[] = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= days; d++) cells.push(`${year}${String(mon).padStart(2, "0")}${String(d).padStart(2, "0")}`);
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function fmt(v?: number | null, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  return Number(v).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}

function pctClass(v?: number | null) {
  if (v === null || v === undefined || Number.isNaN(v)) return "flat";
  if (v > 0) return "up";
  if (v < 0) return "down";
  return "flat";
}

function maybeNum(v: string) {
  if (!v.trim()) return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function maybeScaled(v: string, scale: number) {
  const n = maybeNum(v);
  return n === undefined ? undefined : n * scale;
}

type MarketFilterValues = {
  q: string;
  market: string;
  min_close: string;
  max_close: string;
  min_amount: string;
  max_amount: string;
  min_vol: string;
  max_vol: string;
  min_total_mv: string;
  max_total_mv: string;
  min_turnover_rate: string;
  max_turnover_rate: string;
  min_pe: string;
  max_pe: string;
  min_pb: string;
  max_pb: string;
};

const EMPTY_FILTERS: MarketFilterValues = {
  q: "",
  market: "",
  min_close: "",
  max_close: "",
  min_amount: "",
  max_amount: "",
  min_vol: "",
  max_vol: "",
  min_total_mv: "",
  max_total_mv: "",
  min_turnover_rate: "",
  max_turnover_rate: "",
  min_pe: "",
  max_pe: "",
  min_pb: "",
  max_pb: ""
};

const STOCK_COLUMNS: Array<{ key: string; label: string; numeric?: boolean }> = [
  { key: "ts_code", label: "代码" },
  { key: "name", label: "名称" },
  { key: "market", label: "板块" },
  { key: "close", label: "最新", numeric: true },
  { key: "pct_chg", label: "当日涨跌幅(%)", numeric: true },
  { key: "amount", label: "成交额(亿元)", numeric: true },
  { key: "total_mv", label: "总市值(亿元)", numeric: true },
  { key: "turnover_rate", label: "换手率(%)", numeric: true },
  { key: "pe", label: "PE", numeric: true },
  { key: "pb", label: "PB", numeric: true }
];

export default function App() {
  const [activeNav, setActiveNav] = useState<"market" | "pull">("market");
  const [lastOpen, setLastOpen] = useState<string | null>(null);

  const todayKey = ymd(new Date());

  const [marketDate, setMarketDate] = useState<string>(todayKey);
  const [marketLoading, setMarketLoading] = useState<boolean>(false);
  const [marketIndices, setMarketIndices] = useState<IndexSnapshot[]>([]);
  const [marketItems, setMarketItems] = useState<MarketStockItem[]>([]);
  const [marketTotal, setMarketTotal] = useState<number>(0);
  const [marketPage, setMarketPage] = useState<number>(1);
  const [marketPageSize, setMarketPageSize] = useState<number>(30);
  const [marketSortBy, setMarketSortBy] = useState<string>("amount");
  const [marketSortOrder, setMarketSortOrder] = useState<"asc" | "desc">("desc");
  const [marketFiltersDraft, setMarketFiltersDraft] = useState<MarketFilterValues>(EMPTY_FILTERS);
  const [marketFiltersApplied, setMarketFiltersApplied] = useState<MarketFilterValues>(EMPTY_FILTERS);

  const [pullMonth, setPullMonth] = useState<string>(() => monthKeyOf(new Date()));
  const [calendarDays, setCalendarDays] = useState<CalendarDayStatus[]>([]);
  const [selectedPullDate, setSelectedPullDate] = useState<string>(() => ymd(new Date()));
  const [pullMessage, setPullMessage] = useState<string>("");
  const [pulling, setPulling] = useState<boolean>(false);
  const [monthPulling, setMonthPulling] = useState<boolean>(false);
  const [monthMessage, setMonthMessage] = useState<string>("");
  const [unresolvedItems, setUnresolvedItems] = useState<Array<{ ts_code: string; name?: string }>>([]);
  const [showMonthPicker, setShowMonthPicker] = useState<boolean>(false);
  const [runningPullProgress, setRunningPullProgress] = useState<Record<string, number>>({});

  useEffect(() => {
    getLastOpen().then((d) => {
      if (!d) return;
      setLastOpen(d);
      setMarketDate(d);
      setSelectedPullDate(d);
      setPullMonth(d.slice(0, 6));
    });
  }, []);

  useEffect(() => {
    if (activeNav !== "market" || !marketDate) return;
    let disposed = false;
    setMarketLoading(true);

    getMarketOverview({
      date: marketDate,
      page: marketPage,
      page_size: marketPageSize,
      sort_by: marketSortBy,
      sort_order: marketSortOrder,
      q: marketFiltersApplied.q || undefined,
      market: marketFiltersApplied.market || undefined,
      min_close: maybeNum(marketFiltersApplied.min_close),
      max_close: maybeNum(marketFiltersApplied.max_close),
      min_amount: maybeScaled(marketFiltersApplied.min_amount, 100000),
      max_amount: maybeScaled(marketFiltersApplied.max_amount, 100000),
      min_vol: maybeNum(marketFiltersApplied.min_vol),
      max_vol: maybeNum(marketFiltersApplied.max_vol),
      min_total_mv: maybeScaled(marketFiltersApplied.min_total_mv, 10000),
      max_total_mv: maybeScaled(marketFiltersApplied.max_total_mv, 10000),
      min_turnover_rate: maybeNum(marketFiltersApplied.min_turnover_rate),
      max_turnover_rate: maybeNum(marketFiltersApplied.max_turnover_rate),
      min_pe: maybeNum(marketFiltersApplied.min_pe),
      max_pe: maybeNum(marketFiltersApplied.max_pe),
      min_pb: maybeNum(marketFiltersApplied.min_pb),
      max_pb: maybeNum(marketFiltersApplied.max_pb)
    })
      .then((data) => {
        if (disposed) return;
        setMarketIndices(data.indices || []);
        setMarketItems(data.items || []);
        setMarketTotal(Number(data.total || 0));
      })
      .finally(() => {
        if (!disposed) setMarketLoading(false);
      });

    return () => {
      disposed = true;
    };
  }, [
    activeNav,
    marketDate,
    marketPage,
    marketPageSize,
    marketSortBy,
    marketSortOrder,
    marketFiltersApplied
  ]);

  const marketTotalPages = Math.max(1, Math.ceil(marketTotal / marketPageSize));
  useEffect(() => {
    if (marketPage > marketTotalPages) setMarketPage(marketTotalPages);
  }, [marketPage, marketTotalPages]);

  useEffect(() => {
    if (activeNav !== "pull" || !pullMonth) {
      setRunningPullProgress({});
      return;
    }
    let disposed = false;

    const refresh = async () => {
      const [data, tasks] = await Promise.all([getCalendarStatus(pullMonth), getAdminTasks(undefined, 200)]);
      if (disposed) return;
      setCalendarDays(data.days || []);
      const progressByDate: Record<string, number> = {};
      (tasks.items || [])
        .filter((t) => t.mode === "full_day" && (t.status === "queued" || t.status === "running"))
        .forEach((t) => {
          const pct = Math.max(0, Math.min(100, Number(t.progress?.percent ?? 0)));
          if (progressByDate[t.date] === undefined || pct > progressByDate[t.date]) {
            progressByDate[t.date] = pct;
          }
        });
      setRunningPullProgress(progressByDate);
    };

    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [activeNav, pullMonth]);

  useEffect(() => {
    if (activeNav !== "pull" || !selectedPullDate) {
      setUnresolvedItems([]);
      return;
    }
    let disposed = false;
    getUnresolvedStocks(selectedPullDate, 50).then((res) => {
      if (!disposed) setUnresolvedItems(res.items || []);
    });
    return () => {
      disposed = true;
    };
  }, [activeNav, selectedPullDate, calendarDays]);

  useEffect(() => {
    if (activeNav !== "pull" || calendarDays.length === 0) return;
    const exists = selectedPullDate && calendarDays.some((d) => d.date === selectedPullDate);
    if (exists) return;

    let nextDate: string | undefined;
    if (lastOpen && calendarDays.some((d) => d.date === lastOpen)) {
      nextDate = lastOpen;
    } else {
      const openDays = calendarDays
        .filter((d) => d.is_open && d.date <= todayKey)
        .map((d) => d.date)
        .sort((a, b) => a.localeCompare(b));
      nextDate = openDays[openDays.length - 1];
      if (!nextDate) {
        const fallback = [...calendarDays].sort((a, b) => a.date.localeCompare(b.date));
        nextDate = fallback[fallback.length - 1]?.date;
      }
    }
    if (nextDate && nextDate !== selectedPullDate) {
      setSelectedPullDate(nextDate);
    }
  }, [activeNav, calendarDays, selectedPullDate, lastOpen, todayKey]);

  const dayMap = useMemo(() => {
    const m = new Map<string, CalendarDayStatus>();
    for (const d of calendarDays) m.set(d.date, d);
    return m;
  }, [calendarDays]);

  const selectedDay = selectedPullDate ? dayMap.get(selectedPullDate) || null : null;
  const calendarCells = useMemo(() => (pullMonth ? buildCalendarCells(pullMonth) : []), [pullMonth]);
  const { year: selectedYear, month: selectedMonth } = useMemo(() => parseMonthKey(pullMonth), [pullMonth]);
  const yearOptions = useMemo(() => {
    const current = new Date().getFullYear();
    const years: number[] = [];
    for (let y = current + 2; y >= 2010; y--) years.push(y);
    return years;
  }, []);

  const marketOptions = useMemo(() => {
    const base = ["主板", "创业板", "科创板", "北交所"];
    const dynamic = marketItems.map((r) => r.market).filter(Boolean) as string[];
    return Array.from(new Set([...base, ...dynamic]));
  }, [marketItems]);

  function onSort(field: string) {
    if (marketSortBy === field) {
      setMarketSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setMarketSortBy(field);
      setMarketSortOrder(field === "ts_code" || field === "name" || field === "market" ? "asc" : "desc");
    }
    setMarketPage(1);
  }

  async function onPullDay(date: string) {
    setPulling(true);
    try {
      const res = await triggerFullDaySync(date);
      setPullMessage(`已提交 ${date} 拉取任务${res.task_id ? `，任务ID: ${res.task_id}` : ""}`);
      setRunningPullProgress((prev) => ({ ...prev, [date]: Math.max(1, prev[date] ?? 0) }));
    } catch {
      setPullMessage(`提交 ${date} 拉取任务失败`);
    } finally {
      setPulling(false);
      const data = await getCalendarStatus(pullMonth);
      setCalendarDays(data.days || []);
    }
  }

  async function onClearDay(date: string) {
    setPulling(true);
    try {
      const res = await clearDayData(date);
      setPullMessage(
        `已清除 ${res.date} 数据：日线 ${res.daily_deleted} 条，日线指标 ${res.daily_basic_deleted ?? 0} 条，指数 ${res.index_deleted} 条，停牌 ${res.suspend_deleted} 条`
      );
      setRunningPullProgress((prev) => {
        const next = { ...prev };
        delete next[date];
        return next;
      });
    } catch {
      setPullMessage(`清除 ${date} 数据失败`);
    } finally {
      setPulling(false);
      const data = await getCalendarStatus(pullMonth);
      setCalendarDays(data.days || []);
    }
  }

  async function onPullMonth() {
    if (!calendarDays.length) return;
    setMonthPulling(true);
    let skippedFuture = 0;
    let skippedClosed = 0;
    let skippedRunning = 0;
    let queued = 0;
    let failed = 0;
    const queuedDates: string[] = [];

    try {
      const candidates = [...calendarDays].sort((a, b) => a.date.localeCompare(b.date));
      for (const day of candidates) {
        if (!day.is_open) {
          skippedClosed += 1;
          continue;
        }
        if (day.date > todayKey) {
          skippedFuture += 1;
          continue;
        }
        if (runningPullProgress[day.date] !== undefined) {
          skippedRunning += 1;
          continue;
        }
        try {
          await triggerFullDaySync(day.date);
          queued += 1;
          queuedDates.push(day.date);
        } catch {
          failed += 1;
        }
      }
      if (queuedDates.length > 0) {
        setRunningPullProgress((prev) => {
          const next = { ...prev };
          queuedDates.forEach((d) => {
            next[d] = Math.max(1, next[d] ?? 0);
          });
          return next;
        });
      }
      setMonthMessage(
        `本月批量提交：${queued} 天，失败 ${failed} 天，跳过未来 ${skippedFuture} 天，跳过休市 ${skippedClosed} 天，已在拉取 ${skippedRunning} 天`
      );
    } finally {
      setMonthPulling(false);
      const data = await getCalendarStatus(pullMonth);
      setCalendarDays(data.days || []);
    }
  }

  const expectedCount = selectedDay ? Number(selectedDay.expected_stock_count ?? 0) : 0;
  const indexExpectedCount = selectedDay ? Number(selectedDay.index_expected_count ?? 5) : 5;
  const fetchedCount = selectedDay ? Number(selectedDay.daily_stock_count ?? 0) : 0;
  const indexFetchedCount = selectedDay ? Number(selectedDay.index_daily_count ?? 0) : 0;
  const indexComplete = selectedDay ? Boolean(selectedDay.index_complete ?? false) : false;
  const suspendedCount = selectedDay ? Number(selectedDay.suspended_stock_count ?? 0) : 0;
  const completedCount = selectedDay
    ? Number(selectedDay.completed_stock_count ?? Math.min(expectedCount, fetchedCount + suspendedCount))
    : 0;
  const unresolvedCount = selectedDay
    ? Number(selectedDay.unresolved_stock_count ?? Math.max(expectedCount - completedCount, 0))
    : 0;
  const hasPulledData = fetchedCount > 0 || suspendedCount > 0 || indexFetchedCount > 0;
  const isSelectedFuture = Boolean(selectedDay && selectedDay.date > todayKey);
  const isSelectedRunning = Boolean(selectedDay && runningPullProgress[selectedDay.date] !== undefined);
  const stockProgressPct =
    expectedCount > 0 ? Math.min(100, Number(((completedCount / expectedCount) * 100).toFixed(2))) : 0;
  const progressStatus = !selectedDay
    ? { text: "未选择日期", cls: "idle" }
    : !selectedDay.is_open
      ? { text: "休市", cls: "closed" }
      : isSelectedFuture
        ? { text: "未来", cls: "idle" }
        : isSelectedRunning
          ? { text: "拉取中", cls: "working" }
          : !hasPulledData
            ? { text: "未开始", cls: "idle" }
            : unresolvedCount === 0 && indexComplete
              ? { text: "已完成", cls: "done" }
              : { text: "进行中", cls: "working" };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">Growth</div>
        <button className={`nav-item ${activeNav === "market" ? "active" : ""}`} onClick={() => setActiveNav("market")}>
          行情展示
        </button>
        <button className={`nav-item ${activeNav === "pull" ? "active" : ""}`} onClick={() => setActiveNav("pull")}>
          数据拉取
        </button>
        <div className="sidebar-foot">侧边栏已预留扩展位</div>
      </aside>

      <main className="main">
        <div className="page">
          {activeNav === "market" ? (
            <>
              <header className="topbar">
                <div className="brand">行情展示</div>
                <div className="market-date-picker">
                  <button
                    className="month-nav-btn"
                    onClick={() => {
                      setMarketDate((prev) => shiftDayKey(prev, -1));
                      setMarketPage(1);
                    }}
                    aria-label="前一天"
                  >
                    ‹
                  </button>
                  <input
                    type="date"
                    value={toDateInput(marketDate)}
                    onChange={(e) => {
                      const d = fromDateInput(e.target.value);
                      if (d) {
                        setMarketDate(d);
                        setMarketPage(1);
                      }
                    }}
                  />
                  <button
                    className="month-nav-btn"
                    onClick={() => {
                      setMarketDate((prev) => (prev >= todayKey ? prev : shiftDayKey(prev, 1)));
                      setMarketPage(1);
                    }}
                    aria-label="后一天"
                  >
                    ›
                  </button>
                  <button
                    className="today-btn"
                    onClick={() => {
                      setMarketDate(lastOpen || todayKey);
                      setMarketPage(1);
                    }}
                  >
                    今天
                  </button>
                </div>
              </header>

              <section className="panel">
                <div className="panel-title">指数概览（{marketDate}）</div>
                {marketIndices.length === 0 ? (
                  <div className="ops-hint">该日期暂无指数数据，请先拉取数据。</div>
                ) : (
                  <div className="index-grid">
                    {marketIndices.map((idx) => (
                      <div key={idx.ts_code} className="index-card">
                        <div className="index-head">
                          <div className="index-name">{idx.name}</div>
                          <div className="index-code">{idx.ts_code}</div>
                        </div>
                        <div className={`index-close ${pctClass(idx.pct_chg)}`}>{fmt(idx.close)}</div>
                        <div className={`index-change ${pctClass(idx.pct_chg)}`}>
                          {idx.pct_chg === null || idx.pct_chg === undefined
                            ? "-"
                            : `${fmt(idx.change)} (${fmt(idx.pct_chg)}%)`}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="panel">
                <div className="panel-title">股票列表（已拉取数据）</div>
                <div className="market-filter-grid">
                  <input
                    placeholder="代码/名称/拼音"
                    value={marketFiltersDraft.q}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, q: e.target.value }))}
                  />
                  <select
                    value={marketFiltersDraft.market}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, market: e.target.value }))}
                  >
                    <option value="">全部板块</option>
                    {marketOptions.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="收盘价 ≥"
                    value={marketFiltersDraft.min_close}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, min_close: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="收盘价 ≤"
                    value={marketFiltersDraft.max_close}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, max_close: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="成交额(亿元) ≥"
                    value={marketFiltersDraft.min_amount}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, min_amount: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="成交额(亿元) ≤"
                    value={marketFiltersDraft.max_amount}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, max_amount: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="成交量 ≥"
                    value={marketFiltersDraft.min_vol}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, min_vol: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="成交量 ≤"
                    value={marketFiltersDraft.max_vol}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, max_vol: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="总市值(亿元) ≥"
                    value={marketFiltersDraft.min_total_mv}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, min_total_mv: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="总市值(亿元) ≤"
                    value={marketFiltersDraft.max_total_mv}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, max_total_mv: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="换手率(%) ≥"
                    value={marketFiltersDraft.min_turnover_rate}
                    onChange={(e) =>
                      setMarketFiltersDraft((p) => ({ ...p, min_turnover_rate: e.target.value }))
                    }
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="换手率(%) ≤"
                    value={marketFiltersDraft.max_turnover_rate}
                    onChange={(e) =>
                      setMarketFiltersDraft((p) => ({ ...p, max_turnover_rate: e.target.value }))
                    }
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="PE ≥"
                    value={marketFiltersDraft.min_pe}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, min_pe: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="PE ≤"
                    value={marketFiltersDraft.max_pe}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, max_pe: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="PB ≥"
                    value={marketFiltersDraft.min_pb}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, min_pb: e.target.value }))}
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="PB ≤"
                    value={marketFiltersDraft.max_pb}
                    onChange={(e) => setMarketFiltersDraft((p) => ({ ...p, max_pb: e.target.value }))}
                  />
                  <select
                    value={marketPageSize}
                    onChange={(e) => {
                      setMarketPageSize(Number(e.target.value));
                      setMarketPage(1);
                    }}
                  >
                    <option value={30}>每页 30</option>
                    <option value={50}>每页 50</option>
                    <option value={100}>每页 100</option>
                  </select>
                  <button
                    onClick={() => {
                      setMarketFiltersApplied(marketFiltersDraft);
                      setMarketPage(1);
                    }}
                  >
                    应用筛选
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() => {
                      setMarketFiltersDraft(EMPTY_FILTERS);
                      setMarketFiltersApplied(EMPTY_FILTERS);
                      setMarketPage(1);
                    }}
                  >
                    重置
                  </button>
                </div>

                <div className="market-table-wrap">
                  <table className="market-table">
                    <thead>
                      <tr>
                        {STOCK_COLUMNS.map((col) => (
                          <th key={col.key}>
                            <button className="th-btn" onClick={() => onSort(col.key)}>
                              {col.label}
                              <span className="sort-indicator">
                                {marketSortBy === col.key ? (marketSortOrder === "asc" ? "↑" : "↓") : "↕"}
                              </span>
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {marketLoading ? (
                        <tr>
                          <td colSpan={STOCK_COLUMNS.length} className="table-empty">
                            加载中...
                          </td>
                        </tr>
                      ) : marketItems.length === 0 ? (
                        <tr>
                          <td colSpan={STOCK_COLUMNS.length} className="table-empty">
                            当日暂无已拉取股票数据
                          </td>
                        </tr>
                      ) : (
                        marketItems.map((item) => (
                          <tr key={item.ts_code}>
                            <td>{item.ts_code}</td>
                            <td>{item.name || "-"}</td>
                            <td>{item.market || "-"}</td>
                            <td>{fmt(item.close)}</td>
                            <td>
                              {item.pct_chg === null || item.pct_chg === undefined ? "-" : `${fmt(item.pct_chg, 2)}%`}
                            </td>
                            <td>{item.amount === null || item.amount === undefined ? "-" : fmt(item.amount / 100000, 2)}</td>
                            <td>
                              {item.total_mv === null || item.total_mv === undefined ? "-" : fmt(item.total_mv / 10000, 0)}
                            </td>
                            <td>{fmt(item.turnover_rate, 2)}</td>
                            <td>{fmt(item.pe, 2)}</td>
                            <td>{fmt(item.pb, 2)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="market-table-foot">
                  <div>
                    共 {marketTotal} 条，第 {marketPage} / {marketTotalPages} 页
                  </div>
                  <div className="pager">
                    <button disabled={marketPage <= 1} onClick={() => setMarketPage(1)}>
                      首页
                    </button>
                    <button disabled={marketPage <= 1} onClick={() => setMarketPage((p) => Math.max(1, p - 1))}>
                      上一页
                    </button>
                    <button
                      disabled={marketPage >= marketTotalPages}
                      onClick={() => setMarketPage((p) => Math.min(marketTotalPages, p + 1))}
                    >
                      下一页
                    </button>
                    <button disabled={marketPage >= marketTotalPages} onClick={() => setMarketPage(marketTotalPages)}>
                      末页
                    </button>
                  </div>
                </div>
              </section>
            </>
          ) : (
            <>
              <header className="topbar">
                <div className="brand">数据拉取</div>
              </header>

              <section className="panel calendar-panel">
                <div className="panel-title">月度日历（交易日/数据状态）</div>
                <div className="calendar-toolbar">
                  <button
                    className="month-nav-btn"
                    onClick={() => {
                      setPullMonth((prev) => shiftMonth(prev, -1));
                      setShowMonthPicker(false);
                    }}
                    aria-label="上个月"
                  >
                    ‹
                  </button>
                  <button
                    className="month-title-btn"
                    onClick={() => setShowMonthPicker((v) => !v)}
                    aria-label="选择月份与年份"
                  >
                    <span>{formatMonthLabel(pullMonth)}</span>
                    <span className={`chev ${showMonthPicker ? "open" : ""}`}>▾</span>
                  </button>
                  <button
                    className="month-nav-btn"
                    onClick={() => {
                      setPullMonth((prev) => shiftMonth(prev, 1));
                      setShowMonthPicker(false);
                    }}
                    aria-label="下个月"
                  >
                    ›
                  </button>
                </div>
                {showMonthPicker && (
                  <div className="month-popover">
                    <div className="picker-row">
                      <span className="picker-label">年份</span>
                      <select
                        className="year-select"
                        value={selectedYear}
                        onChange={(e) => setPullMonth(buildMonthKey(Number(e.target.value), selectedMonth))}
                      >
                        {yearOptions.map((y) => (
                          <option key={y} value={y}>
                            {y}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="picker-row picker-months">
                      <span className="picker-label">月份</span>
                      <div className="month-chip-grid">
                        {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                          <button
                            key={m}
                            className={`month-chip ${m === selectedMonth ? "active" : ""}`}
                            onClick={() => {
                              setPullMonth(buildMonthKey(selectedYear, m));
                              setShowMonthPicker(false);
                            }}
                          >
                            {m}月
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
                <div className="month-batch">
                  <div className="month-batch-copy">
                    <div className="month-batch-title">本月批量拉取</div>
                    <div className="month-batch-desc">已拉取日期会重新拉取，未来交易日和休市日自动跳过。</div>
                  </div>
                  <button className="month-batch-btn" disabled={monthPulling} onClick={onPullMonth}>
                    {monthPulling ? "提交中..." : "拉取本月数据"}
                  </button>
                </div>
                {monthMessage && <div className="ops-hint">{monthMessage}</div>}
                <div className="calendar-head">
                  {["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map((w) => (
                    <div key={w} className="calendar-week">
                      {w}
                    </div>
                  ))}
                </div>
                <div className="calendar-grid">
                  {calendarCells.map((d, i) => {
                    if (!d) return <div key={`empty-${i}`} className="day-cell empty" />;
                    const row = dayMap.get(d);
                    if (!row) {
                      return (
                        <button key={d} className="day-cell unknown" disabled>
                          <div>{Number(d.slice(-2))}</div>
                          <div className="day-meta">无数据</div>
                        </button>
                      );
                    }
                    const isFuture = d > todayKey;
                    const runningPct = runningPullProgress[d];
                    const isRunning = runningPct !== undefined;
                    const progressNum = Math.max(0, Math.min(100, Number(runningPct ?? 0)));
                    const tag = !row.is_open
                      ? "休市"
                      : isFuture
                        ? "未来"
                        : isRunning
                          ? "拉取中"
                          : row.is_data_complete
                            ? "已拉取"
                            : row.has_any_data
                              ? "部分"
                              : "未拉取";
                    const cls = !row.is_open
                      ? "closed"
                      : isFuture
                        ? "future"
                        : isRunning
                          ? "running"
                          : row.is_data_complete
                            ? "done"
                            : row.has_any_data
                              ? "partial"
                              : "todo";
                    const spinnerStyle =
                      isRunning && !isFuture
                        ? ({
                            "--progress": `${progressNum.toFixed(0)}%`,
                            "--progress-angle": `${(progressNum * 3.6).toFixed(1)}deg`,
                            "--progress-glow": `${(0.18 + (progressNum / 100) * 0.52).toFixed(3)}`,
                            "--progress-shadow": `${(0.2 + (progressNum / 100) * 0.55).toFixed(3)}`
                          } as CSSProperties)
                        : undefined;
                    return (
                      <button
                        key={d}
                        className={`day-cell ${cls} ${selectedPullDate === d ? "selected" : ""}`}
                        onClick={() => setSelectedPullDate(d)}
                      >
                        <div>{Number(d.slice(-2))}</div>
                        <div className="day-meta-row">
                          <div className="day-meta">{tag}</div>
                          {isRunning && !isFuture && <span className="day-spinner" style={spinnerStyle} />}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </section>

              <section className="panel progress-panel">
                <div className="panel-title">拉取进度（数据库覆盖数）</div>
                {!selectedDay ? (
                  <div className="ops-hint">请选择一个日期</div>
                ) : (
                  <>
                    <div className="progress-hero">
                      <div className="progress-main">
                        <div className="progress-meta">
                          <div className="progress-date">日期 {selectedDay.date}</div>
                          <div className={`progress-state ${progressStatus.cls}`}>{progressStatus.text}</div>
                        </div>
                        <div className="progress-count">
                          <span className="done">{completedCount}</span>
                          <span className="total"> / {expectedCount}</span>
                        </div>
                        <div className="progress-caption">股票覆盖（含停牌）</div>
                        <div className="progress-bar">
                          <div className="progress-fill" style={{ width: `${stockProgressPct}%` }} />
                        </div>
                        <div className="progress-foot">
                          <span>进度 {stockProgressPct}%</span>
                          <span>每 5 秒自动刷新</span>
                        </div>
                      </div>
                      <div className="progress-stats">
                        <div className="stat-card">
                          <div className="stat-k">股票总数</div>
                          <div className="stat-v">{expectedCount}</div>
                        </div>
                        <div className="stat-card">
                          <div className="stat-k">日线</div>
                          <div className="stat-v">{fetchedCount}</div>
                        </div>
                        <div className="stat-card">
                          <div className="stat-k">指数</div>
                          <div className="stat-v">
                            {indexFetchedCount}/{indexExpectedCount}
                          </div>
                        </div>
                        <div className="stat-card">
                          <div className="stat-k">停牌</div>
                          <div className="stat-v">{suspendedCount}</div>
                        </div>
                        <div className="stat-card">
                          <div className="stat-k">待确认</div>
                          <div className="stat-v">{unresolvedCount}</div>
                        </div>
                      </div>
                    </div>
                    {selectedDay.is_open && !isSelectedFuture && (
                      <div className="ops-row progress-actions">
                        {isSelectedRunning ? (
                          <button disabled>拉取中...</button>
                        ) : selectedDay.action === "clear" ? (
                          <button
                            className="clear-btn"
                            disabled={pulling || monthPulling}
                            onClick={() => onClearDay(selectedDay.date)}
                          >
                            数据清除
                          </button>
                        ) : (
                          <button disabled={pulling || monthPulling} onClick={() => onPullDay(selectedDay.date)}>
                            拉取数据
                          </button>
                        )}
                      </div>
                    )}
                    <div className="ops-hint">{pullMessage}</div>
                    {hasPulledData && unresolvedCount > 0 && (
                      <div className="ops-hint unresolved-list">
                        待确认股票（前 {unresolvedItems.length} 条）：{" "}
                        {unresolvedItems.map((i) => `${i.ts_code}${i.name ? `(${i.name})` : ""}`).join("，")}
                      </div>
                    )}
                  </>
                )}
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
