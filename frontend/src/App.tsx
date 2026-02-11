import { useEffect, useState } from "react";
import "./styles.css";
import SearchBox from "./components/SearchBox";
import IntradayChart from "./components/IntradayChart";
import KlineChart from "./components/KlineChart";
import type { BarPoint, StockSuggest } from "./api";
import { getIntraday, getKline, getLastOpen, triggerSync } from "./api";

function ymd(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}${m}${day}`;
}

export default function App() {
  const [selected, setSelected] = useState<StockSuggest | null>(null);
  const [intraday, setIntraday] = useState<BarPoint[]>([]);
  const [kline, setKline] = useState<BarPoint[]>([]);
  const [lastOpen, setLastOpen] = useState<string | null>(null);
  const [syncDate, setSyncDate] = useState<string>("");
  const [ratePerMin, setRatePerMin] = useState<number>(480);
  const [syncMessage, setSyncMessage] = useState<string>("");

  useEffect(() => {
    getLastOpen().then(setLastOpen);
  }, []);

  useEffect(() => {
    if (lastOpen) setSyncDate(lastOpen);
  }, [lastOpen]);

  useEffect(() => {
    if (!selected || !lastOpen) return;

    const end = lastOpen;
    const start = ymd(new Date(Date.now() - 120 * 24 * 60 * 60 * 1000));

    getIntraday(selected.ts_code, lastOpen).then(setIntraday);
    getKline(selected.ts_code, start, end).then(setKline);
  }, [selected, lastOpen]);

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">Growth</div>
        <SearchBox onSelect={setSelected} />
      </header>

      <section className="info">
        <div className="title">
          {selected ? `${selected.name || ""} ${selected.ts_code}` : "请选择一只股票"}
        </div>
        <div className="meta">
          最近交易日: {lastOpen || "-"}
        </div>
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
          <label>
            频率(次/分)
            <input
              type="number"
              min={60}
              max={800}
              value={ratePerMin}
              onChange={(e) => setRatePerMin(Number(e.target.value))}
            />
          </label>
          <button
            onClick={async () => {
              setSyncMessage("已提交：基础信息");
              await triggerSync("basic", syncDate, ratePerMin);
            }}
          >
            基础信息
          </button>
          <button
            onClick={async () => {
              setSyncMessage("已提交：交易日历");
              await triggerSync("trade_cal", syncDate, ratePerMin);
            }}
          >
            交易日历
          </button>
          <button
            onClick={async () => {
              setSyncMessage("已提交：日线");
              await triggerSync("daily", syncDate, ratePerMin);
            }}
          >
            日线
          </button>
          <button
            onClick={async () => {
              if (!selected) {
                setSyncMessage("请先选择股票");
                return;
              }
              setSyncMessage(`已提交：分钟线（单股 ${selected.ts_code}）`);
              await triggerSync("minute", syncDate, ratePerMin, selected.ts_code);
            }}
          >
            分钟线（单股）
          </button>
          <button
            className="danger"
            onClick={async () => {
              setSyncMessage("已提交：分钟线（全市场，耗时）");
              await triggerSync("minute", syncDate, ratePerMin);
            }}
          >
            分钟线（全市场）
          </button>
        </div>
        <div className="ops-hint">{syncMessage}</div>
      </section>

      <section className="grid">
        <div className="panel">
          <div className="panel-title">分时</div>
          <IntradayChart data={intraday} />
        </div>
        <div className="panel">
          <div className="panel-title">K线</div>
          <KlineChart data={kline} />
        </div>
      </section>
    </div>
  );
}
