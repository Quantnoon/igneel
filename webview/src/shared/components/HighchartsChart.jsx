import Highcharts from "highcharts/highstock";
import { useEffect, useRef } from "react";

/**
 * React lifecycle host for the packaged Highcharts runtime. Keeping chart
 * creation here avoids the adapter's dynamic ESM series loader, which can
 * initialize a separate incomplete series registry under Vite.
 */
export function HighchartsChart({ active = true, className, options, stock = false, ...props }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    const createChart = stock ? Highcharts.stockChart : Highcharts.chart;
    chartRef.current = createChart(container, options);
    return () => {
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, [stock]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.update(options, true, true);
    window.requestAnimationFrame(() => chart.reflow());
  }, [options]);

  useEffect(() => {
    if (active) window.requestAnimationFrame(() => chartRef.current?.reflow());
  }, [active]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(() => chartRef.current?.reflow());
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  return <div ref={containerRef} className={className} {...props} />;
}
