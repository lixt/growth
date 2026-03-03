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
  index_expected_count: number;
  daily_stock_count: number;
  index_daily_count: number;
  index_complete: boolean;
  suspended_stock_count: number;
  completed_stock_count: number;
  unresolved_stock_count: number;
  completion_rate: number;
  has_any_data: boolean;
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

export type AdminTask = {
  id: string;
  mode: string;
  date: string;
  status: "queued" | "running" | "success" | "failed";
  progress?: {
    done: number;
    total: number;
    percent: number;
  };
};

export type IndexSnapshot = {
  ts_code: string;
  name: string;
  trade_date: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  change?: number;
  pct_chg?: number;
  vol?: number;
  amount?: number;
};

export type MarketStockItem = {
  ts_code: string;
  name?: string;
  symbol?: string;
  market?: string;
  list_date?: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  pct_chg?: number;
  vol?: number;
  amount?: number;
  turnover_rate?: number;
  pe?: number;
  pb?: number;
  total_mv?: number;
  circ_mv?: number;
};

export type MarketOverviewResponse = {
  date: string;
  indices: IndexSnapshot[];
  page: number;
  page_size: number;
  total: number;
  items: MarketStockItem[];
};

export type IndexSnapshotResponse = {
  date: string;
  indices: IndexSnapshot[];
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
  mode: "basic" | "trade_cal" | "daily" | "index",
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
    const indexExpected = Number(d.index_expected_count ?? 5);
    const daily = Number(d.daily_stock_count ?? 0);
    const indexDaily = Number(d.index_daily_count ?? 0);
    const indexComplete = Boolean(d.index_complete ?? indexDaily >= indexExpected);
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
      index_expected_count: indexExpected,
      daily_stock_count: daily,
      index_daily_count: indexDaily,
      index_complete: indexComplete,
      suspended_stock_count: suspended,
      completed_stock_count: completed,
      unresolved_stock_count: unresolved,
      completion_rate: rate,
      has_any_data: Boolean(d.has_any_data ?? (daily > 0 || suspended > 0 || indexDaily > 0))
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
): Promise<{
  status: string;
  date: string;
  daily_deleted: number;
  daily_basic_deleted?: number;
  index_deleted: number;
  suspend_deleted: number;
}> {
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

export async function getAdminTasks(
  status?: "queued" | "running" | "success" | "failed",
  limit = 200
): Promise<{ items: AdminTask[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  const res = await fetch(`${API_BASE}/api/admin/tasks?${params.toString()}`);
  if (!res.ok) return { items: [] };
  const data = await res.json();
  return { items: data.items || [] };
}

export async function getMarketOverview(params: {
  date: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  q?: string;
  market?: string;
  min_close?: number;
  max_close?: number;
  min_amount?: number;
  max_amount?: number;
  min_vol?: number;
  max_vol?: number;
  min_total_mv?: number;
  max_total_mv?: number;
  min_circ_mv?: number;
  max_circ_mv?: number;
  min_turnover_rate?: number;
  max_turnover_rate?: number;
  min_pe?: number;
  max_pe?: number;
  min_pb?: number;
  max_pb?: number;
}): Promise<MarketOverviewResponse> {
  const query = new URLSearchParams({ date: params.date });
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);
  if (params.q) query.set("q", params.q);
  if (params.market) query.set("market", params.market);
  if (params.min_close !== undefined) query.set("min_close", String(params.min_close));
  if (params.max_close !== undefined) query.set("max_close", String(params.max_close));
  if (params.min_amount !== undefined) query.set("min_amount", String(params.min_amount));
  if (params.max_amount !== undefined) query.set("max_amount", String(params.max_amount));
  if (params.min_vol !== undefined) query.set("min_vol", String(params.min_vol));
  if (params.max_vol !== undefined) query.set("max_vol", String(params.max_vol));
  if (params.min_total_mv !== undefined) query.set("min_total_mv", String(params.min_total_mv));
  if (params.max_total_mv !== undefined) query.set("max_total_mv", String(params.max_total_mv));
  if (params.min_circ_mv !== undefined) query.set("min_circ_mv", String(params.min_circ_mv));
  if (params.max_circ_mv !== undefined) query.set("max_circ_mv", String(params.max_circ_mv));
  if (params.min_turnover_rate !== undefined) query.set("min_turnover_rate", String(params.min_turnover_rate));
  if (params.max_turnover_rate !== undefined) query.set("max_turnover_rate", String(params.max_turnover_rate));
  if (params.min_pe !== undefined) query.set("min_pe", String(params.min_pe));
  if (params.max_pe !== undefined) query.set("max_pe", String(params.max_pe));
  if (params.min_pb !== undefined) query.set("min_pb", String(params.min_pb));
  if (params.max_pb !== undefined) query.set("max_pb", String(params.max_pb));
  const res = await fetch(`${API_BASE}/api/market/overview?${query.toString()}`);
  if (!res.ok) {
    return {
      date: params.date,
      indices: [],
      page: params.page || 1,
      page_size: params.page_size || 50,
      total: 0,
      items: []
    };
  }
  return res.json();
}

export async function getIndexSnapshots(date: string): Promise<IndexSnapshotResponse> {
  const res = await fetch(`${API_BASE}/api/data/index_snapshot?date=${encodeURIComponent(date)}`);
  if (!res.ok) {
    return {
      date,
      indices: []
    };
  }
  return res.json();
}
