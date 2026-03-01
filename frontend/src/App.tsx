import { useEffect, useMemo, useState } from "react";
import "./styles.css";
import SearchBox from "./components/SearchBox";
import KlineChart from "./components/KlineChart";
import type { BarPoint, CalendarDayStatus, StockSuggest } from "./api";
import {
  clearDayData,
  getCalendarStatus,
  getKline,
  getLastOpen,
  getUnresolvedStocks,
  triggerFullDaySync,
  triggerSync
} from "./api";

function ymd(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}${m}${day}`;
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

export default function App() {
  const [activeNav, setActiveNav] = useState<"test" | "pull">("test");

  const [selected, setSelected] = useState<StockSuggest | null>(null);
  const [kline, setKline] = useState<BarPoint[]>([]);
  const [lastOpen, setLastOpen] = useState<string | null>(null);
  const [syncDate, setSyncDate] = useState<string>("");
  const [syncMessage, setSyncMessage] = useState<string>("");

  const [pullMonth, setPullMonth] = useState<string>(() => monthKeyOf(new Date()));
  const [calendarDays, setCalendarDays] = useState<CalendarDayStatus[]>([]);
  const [selectedPullDate, setSelectedPullDate] = useState<string>(() => ymd(new Date()));
  const [pullMessage, setPullMessage] = useState<string>("");
  const [pulling, setPulling] = useState<boolean>(false);
  const [unresolvedItems, setUnresolvedItems] = useState<Array<{ ts_code: string; name?: string }>>([]);
  const [showMonthPicker, setShowMonthPicker] = useState<boolean>(false);

  useEffect(() => {
    getLastOpen().then((d) => {
      setLastOpen(d);
      if (d) {
        setSyncDate(d);
      }
    });
  }, []);

  useEffect(() => {
    if (!selected || !lastOpen) return;
    const end = lastOpen;
    const start = ymd(new Date(Date.now() - 120 * 24 * 60 * 60 * 1000));
    getKline(selected.ts_code, start, end).then(setKline);
  }, [selected, lastOpen]);

  useEffect(() => {
    if (activeNav !== "pull" || !pullMonth) return;
    let disposed = false;

    const refresh = async () => {
      const data = await getCalendarStatus(pullMonth);
      if (!disposed) setCalendarDays(data.days || []);
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

  async function onSync(mode: "basic" | "trade_cal" | "daily") {
    const modeText: Record<"basic" | "trade_cal" | "daily", string> = {
      basic: "基础信息",
      trade_cal: "交易日历",
      daily: "日线"
    };
    setSyncMessage(`已提交：${modeText[mode]}`);
    await triggerSync(mode, syncDate);
  }

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

  async function onPullDay(date: string) {
    setPulling(true);
    try {
      const res = await triggerFullDaySync(date);
      setPullMessage(`已提交 ${date} 拉取任务${res.task_id ? `，任务ID: ${res.task_id}` : ""}`);
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
      setPullMessage(`已清除 ${res.date} 数据：日线 ${res.daily_deleted} 条，停牌 ${res.suspend_deleted} 条`);
    } catch {
      setPullMessage(`清除 ${date} 数据失败`);
    } finally {
      setPulling(false);
      const data = await getCalendarStatus(pullMonth);
      setCalendarDays(data.days || []);
    }
  }

  const expectedCount = selectedDay ? Number(selectedDay.expected_stock_count ?? 0) : 0;
  const fetchedCount = selectedDay ? Number(selectedDay.daily_stock_count ?? 0) : 0;
  const suspendedCount = selectedDay ? Number(selectedDay.suspended_stock_count ?? 0) : 0;
  const completedCount = selectedDay
    ? Number(selectedDay.completed_stock_count ?? Math.min(expectedCount, fetchedCount + suspendedCount))
    : 0;
  const unresolvedCount = selectedDay
    ? Number(selectedDay.unresolved_stock_count ?? Math.max(expectedCount - completedCount, 0))
    : 0;
  const hasPulledData = fetchedCount > 0 || suspendedCount > 0;
  const progressPct =
    expectedCount > 0 ? Math.min(100, Number(((completedCount / expectedCount) * 100).toFixed(2))) : 0;
  const progressStatus = !selectedDay
    ? { text: "未选择日期", cls: "idle" }
    : !selectedDay.is_open
      ? { text: "休市", cls: "closed" }
      : !hasPulledData
        ? { text: "未开始", cls: "idle" }
      : unresolvedCount === 0
        ? { text: "已完成", cls: "done" }
        : { text: "进行中", cls: "working" };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">Growth</div>
        <button
          className={`nav-item ${activeNav === "test" ? "active" : ""}`}
          onClick={() => setActiveNav("test")}
        >
          测试功能
        </button>
        <button
          className={`nav-item ${activeNav === "pull" ? "active" : ""}`}
          onClick={() => setActiveNav("pull")}
        >
          数据拉取
        </button>
        <div className="sidebar-foot">侧边栏已预留扩展位</div>
      </aside>

      <main className="main">
        <div className="page">
          {activeNav === "test" ? (
            <>
              <header className="topbar">
                <div className="brand">测试功能</div>
                <SearchBox onSelect={setSelected} />
              </header>

              <section className="info">
                <div className="title">
                  {selected ? `${selected.name || ""} ${selected.ts_code}` : "请选择一只股票"}
                </div>
                <div className="meta">最近交易日: {lastOpen || "-"}</div>
              </section>

              <section className="panel ops">
                <div className="panel-title">数据抓取（手动）</div>
                <div className="ops-row">
                  <label>
                    日期
                    <input
                      type="text"
                      value={syncDate}
                      onChange={(e) => setSyncDate(e.target.value)}
                      placeholder="YYYYMMDD"
                    />
                  </label>
                  <button onClick={() => onSync("basic")}>基础信息</button>
                  <button onClick={() => onSync("trade_cal")}>交易日历</button>
                  <button onClick={() => onSync("daily")}>日线</button>
                </div>
                <div className="ops-hint">{syncMessage}</div>
              </section>

              <section className="grid">
                <div className="panel">
                  <div className="panel-title">K线</div>
                  <KlineChart data={kline} />
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
                    const tag = row.is_open ? (row.is_data_complete ? "已拉取" : "未拉取") : "休市";
                    const cls = row.is_open ? (row.is_data_complete ? "done" : "todo") : "closed";
                    return (
                      <button
                        key={d}
                        className={`day-cell ${cls} ${selectedPullDate === d ? "selected" : ""}`}
                        onClick={() => setSelectedPullDate(d)}
                      >
                        <div>{Number(d.slice(-2))}</div>
                        <div className="day-meta">{tag}</div>
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
                        <div className="progress-caption">已覆盖（含停牌）</div>
                        <div className="progress-bar">
                          <div className="progress-fill" style={{ width: `${progressPct}%` }} />
                        </div>
                        <div className="progress-foot">
                          <span>进度 {progressPct}%</span>
                          <span>每 5 秒自动刷新</span>
                        </div>
                      </div>
                      <div className="progress-stats">
                        <div className="stat-card">
                          <div className="stat-k">总数</div>
                          <div className="stat-v">{expectedCount}</div>
                        </div>
                        <div className="stat-card">
                          <div className="stat-k">日线</div>
                          <div className="stat-v">{fetchedCount}</div>
                        </div>
                        <div className="stat-card">
                          <div className="stat-k">停牌</div>
                          <div className="stat-v">{suspendedCount}</div>
                        </div>
                        {hasPulledData && (
                          <div className="stat-card">
                            <div className="stat-k">待确认</div>
                            <div className="stat-v">{unresolvedCount}</div>
                          </div>
                        )}
                      </div>
                    </div>
                    {selectedDay.is_open && (
                      <div className="ops-row progress-actions">
                        {selectedDay.action === "clear" ? (
                          <button className="clear-btn" disabled={pulling} onClick={() => onClearDay(selectedDay.date)}>
                            数据清除
                          </button>
                        ) : (
                          <button disabled={pulling} onClick={() => onPullDay(selectedDay.date)}>
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
