import { useEffect, useMemo, useRef, useState } from "react";

import { QFChart } from "@qfo/qfchart";
import { BarChart3 } from "lucide-react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert } from "../../shared/components/Alert.jsx";
import { fetchText } from "../../shared/api/fetch-resource.js";
import { availableMarketTimeframes, convertMarketData } from "../../shared/lib/market-data.js";
import { flattenResults } from "../backtest-results/lib/backtest-results-data.js";
import { buildBacktestTradesDrawing, backtestTradesRenderer } from "./lib/backtest-trade-plots.js";
import { buildConsolidationHotspotsDrawing, CONSOLIDATION_HOTSPOT_COLOR, consolidationHotspotsRenderer } from "./lib/consolidation-hotspots.js";
import { applyIndicatorSeriesColors, buildIndicator, chartAddOptions, indicatorSeriesColorPatches } from "./lib/indicator-plots.js";
import { buildSessionBoundariesDrawing, sessionBoundariesRenderer } from "./lib/session-boundaries.js";
import { priceLevelColumns, visiblePriceRange } from "./lib/visible-price-range.js";
import { useMediaQuery } from "../../shared/hooks/use-media-query.js";

const DEFAULT_ZOOM_START_PERCENT = 75;

export const qfChartOptions = (config) => ({
  title: config.symbol,
  height: "100%",
  titleColor: "#fafafa",
  backgroundColor: "#0a0a0a",
  upColor: "#22c55e",
  downColor: "#ef4444",
  fontColor: "#a3a3a3",
  fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif",
  padding: 0.12,
  dataZoom: { visible: true, position: "top", start: DEFAULT_ZOOM_START_PERCENT, end: 100 },
  grid: { show: true, lineColor: "#262626", lineOpacity: 1, borderColor: "#404040", borderShow: true },
  controls: { collapse: true, maximize: true, fullscreen: true },
  watermark: false,
});

function indicatorLabel(entry) {
  const name = entry.type.toLowerCase().split("_").map((part) => part[0]?.toUpperCase() + part.slice(1)).join(" ");
  const timeframes = [...new Set(entry.columns.map((column) => column.match(/_([A-Za-z0-9]+)$/)?.[1]).filter(Boolean))];
  return timeframes.length > 0 ? `${name} · ${timeframes.join(", ")}` : name;
}

function buildIndicatorItems(records, config, timeframe) {
  const usedIds = new Set();
  const items = [];
  for (const [index, entry] of config.indicators.entries()) {
    const visibilityKey = `${index}:${entry.type}:${entry.columns.join(",")}`;
    if (entry.type === "CONSOLIDATION_HOTSPOT") {
      const drawing = buildConsolidationHotspotsDrawing(records, [entry]);
      if (drawing) items.push({
        id: drawing.id,
        visibilityKey,
        kind: "drawing",
        label: indicatorLabel(entry),
        drawing,
        entry,
        color: CONSOLIDATION_HOTSPOT_COLOR,
      });
      continue;
    }
    const built = buildIndicator(records, entry, usedIds, timeframe);
    if (!built || !Object.values(built.plots).some((plot) => plot.data?.length > 0)) continue;
    items.push({
      id: built.id,
      visibilityKey,
      kind: "indicator",
      label: indicatorLabel(entry),
      entry,
      built,
      color: Object.values(built.plots).find((plot) => typeof plot.options?.color === "string")?.options.color,
    });
  }
  return items;
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

export function MarketChartPage({ active, config, dfPath, resultPath, symbol, symbols = [], onSymbolChange, onViewBacktestResults }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const chartKeyRef = useRef(null);
  const observerRef = useRef(null);
  const [state, setState] = useState({ data: null, error: "", loading: false });
  const [timeframe, setTimeframe] = useState(config.entryTf);
  const [indicatorItems, setIndicatorItems] = useState([]);
  const [indicatorVisibility, setIndicatorVisibility] = useState({});
  const [mobileIndicatorOpen, setMobileIndicatorOpen] = useState(false);
  const [sessionBoundariesVisible, setSessionBoundariesVisible] = useState(true);
  const isMobile = useMediaQuery("(max-width: 767px)");

  const chartData = useMemo(() => {
    if (!state.data) return null;
    try {
      return {
        records: convertMarketData(
          state.data.csvText,
          timeframe,
          state.data.config.indicators.flatMap((indicator) => indicator.columns),
        ),
        error: "",
      };
    } catch (error) {
      return { records: null, error: `Chart initialization failed: ${error.message ?? String(error)}` };
    }
  }, [state.data, timeframe]);

  useEffect(() => {
    if (!active || !dfPath || state.data?.dfPath === dfPath) return undefined;
    let mounted = true;
    const controller = new AbortController();
    setState({ data: null, error: "", loading: true });
    Promise.all([fetchText(dfPath, controller.signal), fetchText(resultPath, controller.signal)])
      .then(([csvText, resultText]) => {
        const trades = flattenResults(JSON.parse(resultText)).find((result) => result.symbol === symbol)?.trades ?? [];
        if (mounted) setState({
          data: { config, csvText, availableTimeframes: availableMarketTimeframes(csvText), trades, dfPath },
          error: "",
          loading: false,
        });
      })
      .catch((error) => {
        if (mounted && error.name !== "AbortError") {
          setState({ data: null, error: `Chart initialization failed: ${error.message ?? String(error)}`, loading: false });
        }
      });
    return () => { mounted = false; controller.abort(); };
  }, [active, config, dfPath, resultPath, symbol, state.data]);

  useEffect(() => {
    const options = state.data?.availableTimeframes ?? [];
    if (options.length > 0 && !options.includes(timeframe)) {
      setTimeframe(options.includes(config.entryTf) ? config.entryTf : options[0]);
    }
  }, [config.entryTf, state.data, timeframe]);

  useEffect(() => {
    if (!active || !state.data || !chartData?.records || !containerRef.current) return;

    const chartKey = `${timeframe}:${isMobile}`;
    if (chartRef.current && chartKeyRef.current !== chartKey) {
      observerRef.current?.disconnect();
      observerRef.current = null;
      chartRef.current.destroy();
      chartRef.current = null;
    }
    if (chartRef.current) return;

    const chart = new QFChart(containerRef.current, qfChartOptions({ ...state.data.config, symbol }));
    chartRef.current = chart;
    chartKeyRef.current = chartKey;
    chart.setMarketData(chartData.records);
    const items = buildIndicatorItems(chartData.records, state.data.config, timeframe);
    setIndicatorItems(items);
    for (const item of items) {
      if (indicatorVisibility[item.visibilityKey] === false) continue;
      if (item.kind === "indicator") {
        chart.addIndicator(item.built.id, item.built.plots, chartAddOptions(item.built.addOptions));
      }
    }
    const patches = indicatorSeriesColorPatches(items.filter((item) => item.kind === "indicator").map((item) => item.built));
    const syncColors = () => applyIndicatorSeriesColors(chart, patches);
    syncColors();
    chart.events.on("chart:updated", syncColors);
    chart.registerDrawingRenderer(backtestTradesRenderer);
    chart.registerDrawingRenderer(sessionBoundariesRenderer);
    chart.registerDrawingRenderer(consolidationHotspotsRenderer);
    const tradesDrawing = buildBacktestTradesDrawing(chartData.records, state.data.trades);
    const sessionBoundariesDrawing = buildSessionBoundariesDrawing(chartData.records);
    // QFChart batches drawings into one ECharts custom series whose dimensions are
    // sized from the first drawing's row, so the drawing with the most points must
    // be added first or its trailing markers are culled by the data zoom window.
    const visibleDrawings = items
      .filter((item) => item.kind === "drawing" && indicatorVisibility[item.visibilityKey] !== false)
      .map((item) => item.drawing);
    const drawings = [sessionBoundariesVisible ? sessionBoundariesDrawing : null, tradesDrawing, ...visibleDrawings]
      .filter(Boolean)
      .sort((left, right) => right.points.length - left.points.length);
    for (const drawing of drawings) chart.addDrawing(drawing);

    observerRef.current = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => chart.resize());
    observerRef.current?.observe(containerRef.current);

    return () => chart.events.off("chart:updated", syncColors);
  }, [active, chartData, isMobile, sessionBoundariesVisible, state.data, timeframe, symbol]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !state.data || !chartData?.records) return undefined;
    const visibleIndicators = indicatorItems
      .filter((item) => indicatorVisibility[item.visibilityKey] !== false)
      .map((item) => item.entry);
    const updatePriceScale = () => applyVisiblePriceScale(chart, chartData.records, visibleIndicators);
    updatePriceScale();
    chart.events.on("chart:dataZoom", updatePriceScale);
    return () => chart.events.off("chart:dataZoom", updatePriceScale);
  }, [chartData, indicatorItems, indicatorVisibility, isMobile, state.data, timeframe]);

  useEffect(() => () => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    chartRef.current?.destroy();
    chartRef.current = null;
    chartKeyRef.current = null;
  }, []);

  useEffect(() => {
    if (active) chartRef.current?.resize();
  }, [active]);

  function setIndicatorShown(item, shown) {
    setIndicatorVisibility((previous) => ({ ...previous, [item.visibilityKey]: shown }));
    const chart = chartRef.current;
    if (!chart) return;
    if (item.kind === "drawing") {
      if (shown) {
        if (!chart.getDrawing?.(item.id)) chart.addDrawing(item.drawing);
      } else {
        chart.removeDrawing(item.id);
      }
    } else if (shown) {
      chart.addIndicator(item.built.id, item.built.plots, chartAddOptions(item.built.addOptions));
    } else {
      chart.removeIndicator(item.id);
    }
  }

  function setSessionBoundariesShown(shown) {
    setSessionBoundariesVisible(shown);
    const chart = chartRef.current;
    if (!chart || !chartData?.records) return;
    const drawing = buildSessionBoundariesDrawing(chartData.records);
    if (!drawing) return;
    if (shown) chart.addDrawing(drawing);
    else chart.removeDrawing(drawing.id);
  }

  const availableTimeframes = state.data?.availableTimeframes ?? [];
  const displayError = state.error || chartData?.error || (state.data && availableTimeframes.length === 0
    ? "Chart data has no timeframe with complete OHLC columns."
    : "");
  return (
    <div className="relative flex h-full min-h-0 w-full flex-col overflow-hidden">
          {displayError && <div className="absolute inset-x-4 top-4 z-30"><Alert kind="error" role="alert">{displayError}</Alert></div>}
          {state.loading && <div className="absolute inset-x-4 top-4 z-10"><Alert role="status">Loading chart data…</Alert></div>}
          <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden bg-[#0a0a0a]">
            <section className="flex min-h-0 min-w-0 flex-1 flex-col" aria-label={`${symbol} market chart`}>
              <div className="flex flex-wrap items-center gap-3 border-b border-foreground/10 px-4 py-2">
                <div className="flex items-center gap-1.5" role="group" aria-label="Chart timeframe">
                  {availableTimeframes.map((option) => (
                    <button
                      key={option}
                      type="button"
                      aria-pressed={timeframe === option}
                      onClick={() => setTimeframe(option)}
                      className={`min-h-10 min-w-12 rounded-lg border px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f8eff] ${timeframe === option ? "border-[#0f8eff]/70 bg-[#0f8eff]/15 text-[#0f8eff] shadow-sm shadow-[#0f8eff]/10" : "border-foreground/10 text-muted-foreground hover:border-foreground/25 hover:bg-foreground/10 hover:text-foreground"}`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
                {symbols.length > 0 && (
                  <Select value={symbol} onValueChange={onSymbolChange}>
                    <SelectTrigger aria-label="Chart symbol" className="h-10! min-w-36 border-foreground/15 bg-[#111111] text-sm text-foreground hover:bg-[#171717]">
                      <SelectValue placeholder="Select symbol" />
                    </SelectTrigger>
                    <SelectContent className="border-foreground/15 bg-[#111111] text-foreground">
                      {symbols.map((option) => <SelectItem key={option} value={option}>{option}</SelectItem>)}
                    </SelectContent>
                  </Select>
                )}
                {isMobile && (
                  <button
                    type="button"
                    aria-expanded={mobileIndicatorOpen}
                    aria-controls="chart-indicator-panel"
                    onClick={() => setMobileIndicatorOpen((open) => !open)}
                    className="ml-auto min-h-10 rounded-lg border border-foreground/15 px-4 text-sm font-semibold text-foreground hover:bg-foreground/10"
                  >
                    Indicators
                  </button>
                )}
                <button
                  type="button"
                  onClick={onViewBacktestResults}
                  className="ml-auto inline-flex min-h-10 items-center gap-2 rounded-md px-2 text-sm font-semibold text-foreground transition-colors hover:bg-foreground/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f8eff] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0a]"
                >
                  <BarChart3 aria-hidden="true" className="size-4 text-[#0f8eff]" />
                  View Backtest Results
                </button>
              </div>
              <div ref={containerRef} className="min-h-0 min-w-0 flex-1 overflow-hidden" aria-label={`${symbol} ${timeframe} candlestick chart`} data-chart-surface="page-background" />
            </section>
            <aside
              id="chart-indicator-panel"
              aria-label="Chart indicators"
              className={isMobile
                ? `${mobileIndicatorOpen ? "absolute inset-x-3 bottom-3 top-14 z-20 block" : "hidden"} overflow-y-auto rounded-lg border border-foreground/15 bg-[#111111]/95 p-3 shadow-xl backdrop-blur`
                : "relative flex w-64 shrink-0 flex-col overflow-y-auto border-l border-foreground/10 bg-[#0d0d0d] p-4"}
            >
              <h2 className="mb-3 text-sm font-semibold text-foreground">Indicators</h2>
              <button
                type="button"
                aria-pressed={sessionBoundariesVisible}
                onClick={() => setSessionBoundariesShown(!sessionBoundariesVisible)}
                className="mb-2 flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm text-foreground/90 hover:bg-foreground/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
              >
                <span aria-hidden="true" className={`size-2 shrink-0 rounded-full bg-zinc-500 ${sessionBoundariesVisible ? "" : "opacity-35"}`} />
                <span className={sessionBoundariesVisible ? "" : "text-muted-foreground line-through"}>Session Boundaries</span>
              </button>
              {indicatorItems.length === 0 ? (
                <p className="text-xs text-muted-foreground">No chart indicators available.</p>
              ) : (
                <ul className="space-y-2">
                  {indicatorItems.map((item) => (
                    <li key={item.visibilityKey}>
                      <button
                        type="button"
                        aria-pressed={indicatorVisibility[item.visibilityKey] !== false}
                        onClick={() => setIndicatorShown(item, indicatorVisibility[item.visibilityKey] === false)}
                        className="flex w-full items-start gap-2 rounded-md px-1 py-1.5 text-left text-sm text-foreground/90 hover:bg-foreground/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
                      >
                        {item.color && <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ backgroundColor: item.color }} aria-hidden="true" />}
                        <span className={indicatorVisibility[item.visibilityKey] === false ? "text-muted-foreground line-through" : ""}>{item.label}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </aside>
          </div>
    </div>
  );
}
