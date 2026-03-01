export type StockSuggest = {
  ts_code: string;
  name?: string;
  symbol?: string;
  cnspell?: string;
};

export type BarPoint = {
  ts_code: string;
  time: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  vol?: number;
  amount?: number;
};

export type CalendarDayStatus = {
  date: string;
  is_open: boolean;
  expected_stock_count: number;
  daily_stock_count: number;
  suspended_stock_count: number;
  completed_stock_count: number;
  unresolved_stock_count: number;
  completion_rate: number;
  is_data_complete: boolean;
  action: "none" | "pull" | "clear";
};

export type CalendarStatusResponse = {
  month: string;
  days: CalendarDayStatus[];
};

export type UnresolvedStockItem = {
  ts_code: string;
  name?: string;
};

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function searchStocks(q: string): Promise<StockSuggest[]> {
  const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
  return res.json();
}

export async function getLastOpen(): Promise<string | null> {
  const res = await fetch(`${API_BASE}/api/trade/last_open`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.date || null;
}

export async function getKline(tsCode: string, start: string, end: string): Promise<BarPoint[]> {
  const res = await fetch(
    `${API_BASE}/api/stock/${encodeURIComponent(tsCode)}/kline?start=${start}&end=${end}`
  );
  if (!res.ok) return [];
  return res.json();
}

export async function triggerSync(
  mode: "basic" | "trade_cal" | "daily",
  date?: string
): Promise<{ status: string }> {
  const params = new URLSearchParams({ mode });
  if (date) params.set("date", date);
  const res = await fetch(`${API_BASE}/api/admin/sync?${params.toString()}`, { method: "POST" });
  if (!res.ok) throw new Error("sync failed");
  return res.json();
}

export async function getCalendarStatus(month: string): Promise<CalendarStatusResponse> {
  const res = await fetch(`${API_BASE}/api/data/calendar?month=${encodeURIComponent(month)}`);
  if (!res.ok) {
    return { month, days: [] };
  }
  const data = await res.json();
  const days = (data.days || []).map((d: any) => {
    const expected = Number(d.expected_stock_count ?? 0);
    const daily = Number(d.daily_stock_count ?? 0);
    const suspended = Number(d.suspended_stock_count ?? 0);
    const completed =
      d.completed_stock_count === undefined || d.completed_stock_count === null
        ? Math.min(expected, daily + suspended)
        : Number(d.completed_stock_count);
    const unresolved =
      d.unresolved_stock_count === undefined || d.unresolved_stock_count === null
        ? daily > 0 || suspended > 0
          ? Math.max(expected - completed, 0)
          : 0
        : Number(d.unresolved_stock_count);
    const rate =
      d.completion_rate === undefined || d.completion_rate === null
        ? expected > 0
          ? Number(((completed / expected) * 100).toFixed(2))
          : 0
        : Number(d.completion_rate);
    return {
      ...d,
      expected_stock_count: expected,
      daily_stock_count: daily,
      suspended_stock_count: suspended,
      completed_stock_count: completed,
      unresolved_stock_count: unresolved,
      completion_rate: rate
    };
  });
  return { month: data.month || month, days };
}

export async function triggerFullDaySync(date: string): Promise<{ status: string; task_id?: string }> {
  const res = await fetch(
    `${API_BASE}/api/admin/sync/full_day?date=${encodeURIComponent(date)}&overwrite=true`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error("full day sync failed");
  return res.json();
}

export async function clearDayData(
  date: string
): Promise<{ status: string; date: string; daily_deleted: number; suspend_deleted: number }> {
  const res = await fetch(`${API_BASE}/api/admin/clear/day?date=${encodeURIComponent(date)}`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("clear day data failed");
  return res.json();
}

export async function getUnresolvedStocks(
  date: string,
  limit = 50
): Promise<{ date: string; items: UnresolvedStockItem[] }> {
  const res = await fetch(
    `${API_BASE}/api/data/day_unresolved?date=${encodeURIComponent(date)}&limit=${encodeURIComponent(String(limit))}`
  );
  if (!res.ok) return { date, items: [] };
  const data = await res.json();
  return { date: data.date || date, items: data.items || [] };
}
