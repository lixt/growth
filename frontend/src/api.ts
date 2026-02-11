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

export async function getIntraday(tsCode: string, date: string): Promise<BarPoint[]> {
  const res = await fetch(`${API_BASE}/api/stock/${encodeURIComponent(tsCode)}/intraday?date=${date}`);
  if (!res.ok) return [];
  return res.json();
}

export async function getKline(tsCode: string, start: string, end: string): Promise<BarPoint[]> {
  const res = await fetch(
    `${API_BASE}/api/stock/${encodeURIComponent(tsCode)}/kline?start=${start}&end=${end}`
  );
  if (!res.ok) return [];
  return res.json();
}

export async function triggerSync(
  mode: "basic" | "trade_cal" | "daily" | "minute",
  date?: string,
  ratePerMin: number = 480,
  tsCode?: string
): Promise<{ status: string }> {
  const params = new URLSearchParams({ mode, rate_per_min: String(ratePerMin) });
  if (date) params.set("date", date);
  if (tsCode) params.set("ts_code", tsCode);
  const res = await fetch(`${API_BASE}/api/admin/sync?${params.toString()}`, { method: "POST" });
  if (!res.ok) throw new Error("sync failed");
  return res.json();
}
