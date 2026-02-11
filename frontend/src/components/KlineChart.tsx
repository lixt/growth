import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { BarPoint } from "../api";

function calcMA(data: BarPoint[], dayCount: number) {
  const result: (number | "-")[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < dayCount) {
      result.push("-");
      continue;
    }
    let sum = 0;
    for (let j = 0; j < dayCount; j++) {
      sum += data[i - j].close || 0;
    }
    result.push(Number((sum / dayCount).toFixed(2)));
  }
  return result;
}

export default function KlineChart({ data }: { data: BarPoint[] }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    chartRef.current = echarts.init(ref.current, "dark");
    const chart = chartRef.current;

    return () => {
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = chartRef.current;

    const category = data.map((d) => (typeof d.time === "string" ? d.time.slice(4, 8) : ""));
    const values = data.map((d) => [d.open || 0, d.close || 0, d.low || 0, d.high || 0]);
    const vols = data.map((d) => d.vol || 0);

    const option: echarts.EChartsOption = {
      backgroundColor: "#111214",
      grid: [
        { left: 44, right: 24, top: 16, height: 180 },
        { left: 44, right: 24, top: 210, height: 60 }
      ],
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" }
      },
      xAxis: [
        { type: "category", data: category, boundaryGap: true, axisLine: { lineStyle: { color: "#333" } } },
        { type: "category", data: category, boundaryGap: true, gridIndex: 1, axisLabel: { show: false }, axisLine: { lineStyle: { color: "#333" } } }
      ],
      yAxis: [
        { scale: true, axisLine: { lineStyle: { color: "#333" } }, splitLine: { lineStyle: { color: "#202226" } } },
        { scale: true, gridIndex: 1, axisLine: { lineStyle: { color: "#333" } }, splitLine: { show: false } }
      ],
      series: [
        {
          type: "candlestick",
          name: "kline",
          data: values,
          itemStyle: {
            color: "#e44",
            color0: "#2db55d",
            borderColor: "#e44",
            borderColor0: "#2db55d"
          },
          xAxisIndex: 0,
          yAxisIndex: 0
        },
        {
          type: "line",
          name: "MA5",
          data: calcMA(data, 5),
          showSymbol: false,
          lineStyle: { width: 1, color: "#f2c14e" }
        },
        {
          type: "line",
          name: "MA10",
          data: calcMA(data, 10),
          showSymbol: false,
          lineStyle: { width: 1, color: "#4aa3ff" }
        },
        {
          type: "line",
          name: "MA20",
          data: calcMA(data, 20),
          showSymbol: false,
          lineStyle: { width: 1, color: "#ff6b6b" }
        },
        {
          type: "bar",
          name: "vol",
          data: vols,
          xAxisIndex: 1,
          yAxisIndex: 1,
          itemStyle: { color: "#3c7" }
        }
      ]
    };

    chart.setOption(option);
  }, [data]);

  return <div className="chart" ref={ref} />;
}
