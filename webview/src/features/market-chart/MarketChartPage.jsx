import { useEffect, useRef, useState } from "react";

import { QFChart } from "@qfo/qfchart";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert } from "../../shared/components/Alert.jsx";
import { fetchText } from "../../shared/api/fetch-resource.js";
import { convertMarketData } from "../../shared/lib/market-data.js";
import { flattenResults } from "../backtest-results/lib/backtest-results-data.js";
import { buildBacktestTradesDrawing, backtestTradesRenderer } from "./lib/backtest-trade-plots.js";
import { applyIndicatorSeriesColors, buildIndicator, chartAddOptions, indicatorSeriesColorPatches } from "./lib/indicator-plots.js";
import { buildSessionBoundariesDrawing, sessionBoundariesRenderer } from "./lib/session-boundaries.js";
import { priceLevelColumns, visiblePriceRange } from "./lib/visible-price-range.js";
import { useMediaQuery } from "../../shared/hooks/use-media-query.js";

const DEFAULT_ZOOM_START_PERCENT = 75;

export const qfChartOptions = (config, isMobile = false) => ({
  title: `${config.symbol} ${config.entryTf}`,
  height: "100%",
  titleColor: "#fafafa",
  backgroundColor: "#0a0a0a",
  upColor: "#22c55e",
  downColor: "#ef4444",
  fontColor: "#a3a3a3",
  fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif",
  padding: 0.12,
  databox: isMobile ? { position: "floating", triggerOn: "click" } : { position: "right", triggerOn: "mousemove" },
  dataZoom: { visible: true, position: "top", start: DEFAULT_ZOOM_START_PERCENT, end: 100 },
  grid: { show: true, lineColor: "#262626", lineOpacity: 1, borderColor: "#404040", borderShow: true },
  controls: { collapse: true, maximize: true, fullscreen: true },
  watermark: false,
});

function renderIndicators(chart, records, config) {
  const usedIds = new Set();
  const builtIndicators = [];
  for (const entry of config.indicators) {
    const built = buildIndicator(records, entry, usedIds, config.entryTf);
    if (!built || !Object.values(built.plots).some((plot) => plot.data?.length > 0)) continue;
    chart.addIndicator(built.id, built.plots, chartAddOptions(built.addOptions));
    builtIndicators.push(built);
  }
  return builtIndicators;
}

export function applyVisiblePriceScale(chart, records, indicators) {
  const echarts = chart.getChart();
  const option = echarts.getOption();
  const zoom = option.dataZoom?.find((entry) => entry.type === "inside" || entry.type === "slider");
  const categories = option.xAxis?.[0]?.data;
  if (!zoom || !Array.isArray(categories)) return null;

  const range = visiblePriceRange(records, priceLevelColumns(indicators), {
    categoryCount: categories.length,
    start: zoom.start,
    end: zoom.end,
  });
  if (!range) return null;
  echarts.setOption({ yAxis: [{ min: range.min, max: range.max }] });
  return range;
}

export function MarketChartPage({ active, config, dfPath, resultPath, symbol }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const chartMobileLayoutRef = useRef(null);
  const observerRef = useRef(null);
  const [state, setState] = useState({ data: null, error: "", loading: false });
  const isMobile = useMediaQuery("(max-width: 767px)");

  useEffect(() => {
    if (!active || !dfPath || state.data?.dfPath === dfPath) return undefined;
    let mounted = true;
    const controller = new AbortController();
    setState({ data: null, error: "", loading: true });
    Promise.all([fetchText(dfPath, controller.signal), fetchText(resultPath, controller.signal)])
      .then(([csvText, resultText]) => {
        const records = convertMarketData(csvText, config.entryTf, config.indicators.flatMap((indicator) => indicator.columns));
        const trades = flattenResults(JSON.parse(resultText)).find((result) => result.symbol === symbol)?.trades ?? [];
        if (mounted) setState({ data: { config, records, trades, dfPath }, error: "", loading: false });
      })
      .catch((error) => {
        if (mounted && error.name !== "AbortError") {
          setState({ data: null, error: `Chart initialization failed: ${error.message ?? String(error)}`, loading: false });
        }
      });
    return () => { mounted = false; controller.abort(); };
  }, [active, config, dfPath, resultPath, symbol, state.data]);

  useEffect(() => {
    if (!active || !state.data || !containerRef.current) return;

    if (chartRef.current && chartMobileLayoutRef.current !== isMobile) {
      observerRef.current?.disconnect();
      observerRef.current = null;
      chartRef.current.destroy();
      chartRef.current = null;
    }
    if (chartRef.current) return;

    const chart = new QFChart(containerRef.current, qfChartOptions({ ...state.data.config, symbol }, isMobile));
    chartRef.current = chart;
    chartMobileLayoutRef.current = isMobile;
    chart.setMarketData(state.data.records);
    const builtIndicators = renderIndicators(chart, state.data.records, state.data.config);
    const patches = indicatorSeriesColorPatches(builtIndicators);
    const syncColors = () => applyIndicatorSeriesColors(chart, patches);
    syncColors();
    chart.events.on("chart:updated", syncColors);
    chart.registerDrawingRenderer(backtestTradesRenderer);
    chart.registerDrawingRenderer(sessionBoundariesRenderer);
    const tradesDrawing = buildBacktestTradesDrawing(state.data.records, state.data.trades);
    const sessionBoundariesDrawing = buildSessionBoundariesDrawing(state.data.records);
    // QFChart batches drawings into one ECharts custom series whose dimensions are
    // sized from the first drawing's row, so the drawing with the most points must
    // be added first or its trailing markers are culled by the data zoom window.
    const drawings = [sessionBoundariesDrawing, tradesDrawing]
      .filter(Boolean)
      .sort((left, right) => right.points.length - left.points.length);
    for (const drawing of drawings) chart.addDrawing(drawing);

    observerRef.current = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => chart.resize());
    observerRef.current?.observe(containerRef.current);

    return () => chart.events.off("chart:updated", syncColors);
  }, [active, isMobile, state.data]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !state.data) return undefined;
    const updatePriceScale = () => applyVisiblePriceScale(chart, state.data.records, state.data.config.indicators);
    updatePriceScale();
    chart.events.on("chart:dataZoom", updatePriceScale);
    return () => chart.events.off("chart:dataZoom", updatePriceScale);
  }, [isMobile, state.data]);

  useEffect(() => () => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    chartRef.current?.destroy();
    chartRef.current = null;
    chartMobileLayoutRef.current = null;
  }, []);

  useEffect(() => {
    if (active) chartRef.current?.resize();
  }, [active]);

  const label = state.data ? symbol : "Backtest chart";
  return (
    <div className="mx-auto flex h-full min-h-0 w-full max-w-[100rem] flex-col overflow-hidden px-4 py-4 sm:px-6 sm:py-5 lg:px-8 lg:py-6">
      <Card className="min-h-0 flex-1">
        <CardContent className="relative flex min-h-0 flex-1">
          {state.error && <div className="absolute inset-x-4 top-4 z-10"><Alert kind="error" role="alert">{state.error}</Alert></div>}
          {state.loading && <div className="absolute inset-x-4 top-4 z-10"><Alert role="status">Loading chart data…</Alert></div>}
          <div ref={containerRef} className="min-h-0 flex-1 overflow-hidden rounded-lg bg-[#0a0a0a] ring-1 ring-foreground/10" aria-label={label} data-chart-surface="page-background" />
        </CardContent>
      </Card>
    </div>
  );
}
