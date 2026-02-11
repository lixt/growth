import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { BarPoint } from "../api";

export default function IntradayChart({ data }: { data: BarPoint[] }) {
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

    const times = data.map((d) => (typeof d.time === "string" ? d.time.slice(11, 16) : ""));
    const prices = data.map((d) => d.close || d.open || 0);
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
        { type: "category", data: times, boundaryGap: false, axisLine: { lineStyle: { color: "#333" } } },
        { type: "category", data: times, boundaryGap: false, gridIndex: 1, axisLabel: { show: false }, axisLine: { lineStyle: { color: "#333" } } }
      ],
      yAxis: [
        { scale: true, axisLine: { lineStyle: { color: "#333" } }, splitLine: { lineStyle: { color: "#202226" } } },
        { scale: true, gridIndex: 1, axisLine: { lineStyle: { color: "#333" } }, splitLine: { show: false } }
      ],
      series: [
        {
          type: "line",
          name: "price",
          data: prices,
          showSymbol: false,
          lineStyle: { color: "#e6e6e6", width: 1.2 },
          xAxisIndex: 0,
          yAxisIndex: 0
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
