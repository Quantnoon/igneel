import { useEffect, useMemo, useRef, useState } from "react";

import { QFChart } from "@qfo/qfchart";
import { BarChart3 } from "lucide-react";

import { Alert } from "../../shared/components/Alert.jsx";
import { fetchCachedText } from "../../shared/api/fetch-cached-text.js";
import { loadCsvDataset } from "../../shared/api/fetch-csv-chunks.js";
import { availableMarketTimeframes, convertMarketData } from "../../shared/lib/market-data.js";
import { prependCsvChunk } from "../../shared/lib/csv-records.js";
import { flattenResults } from "../backtest-results/lib/backtest-results-data.js";
import { buildBacktestTradesDrawing, backtestTradesRenderer } from "./lib/backtest-trade-plots.js";
import { buildConsolidationHotspotsDrawing, CONSOLIDATION_HOTSPOT_COLOR, consolidationHotspotsRenderer } from "./lib/consolidation-hotspots.js";
import { applyIndicatorSeriesColors, buildIndicator, chartAddOptions, indicatorSeriesColorPatches } from "./lib/indicator-plots.js";
import { buildSessionBoundariesDrawing, sessionBoundariesRenderer } from "./lib/session-boundaries.js";
import { priceLevelColumns, visiblePriceRange } from "./lib/visible-price-range.js";
import { useMediaQuery } from "../../shared/hooks/use-media-query.js";
import { MarketChartSkeleton } from "./MarketChartSkeleton.jsx";
import { MarketChartSymbolSelect } from "./MarketChartSymbolSelect.jsx";

const DEFAULT_ZOOM_START_PERCENT = 75;
const CANDLES_PER_CHUNK = 1000;

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

function visibleCategoryRange(chart, records) {
  if (!records.length) return null;
  const option = chart.getChart().getOption();
  const zoom = option.dataZoom?.find((entry) => entry.type === "inside" || entry.type === "slider");
  const categories = option.xAxis?.[0]?.data;
  if (!zoom || !Array.isArray(categories) || categories.length === 0) return null;
  const start = Math.max(0, Math.min(categories.length - 1, Math.floor((zoom.start ?? 0) / 100 * categories.length)));
  const end = Math.max(start, Math.min(categories.length - 1, Math.ceil((zoom.end ?? 100) / 100 * categories.length) - 1));
  return { start: categories[start], end: categories[end] };
}

function isNearLoadedLeftEdge(chart, candleCount) {
  const option = chart.getChart().getOption();
  const zoom = option.dataZoom?.find((entry) => entry.type === "inside" || entry.type === "slider");
  const categories = option.xAxis?.[0]?.data;
  if (!zoom || !Array.isArray(categories) || categories.length === 0) return false;
  const startIndex = Math.floor((zoom.start ?? 0) / 100 * categories.length);
  return startIndex <= Math.min(CANDLES_PER_CHUNK * 0.1, candleCount * 0.1);
}

export function MarketChartPage({ active, visible = true, config, dfPath, resultPath, symbol, symbols = [], onSymbolChange, onViewBacktestResults, pendingSymbol, symbolMenuOpen, onSymbolMenuOpenChange, onChartActivationReady, onChartActivationError }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const chartKeyRef = useRef(null);
  const observerRef = useRef(null);
  const loadedChartRecordsRef = useRef(null);
  const chartContentRef = useRef({ indicators: [], drawingIds: [], colorHandler: null });
  const pagingRef = useRef({ key: "", chunks: null, nextChunkIndex: null, loading: false, exhausted: false });
  const pagingKeyRef = useRef("");
  const [state, setState] = useState({ data: null, error: "", loading: false });
  const [retryAttempt, setRetryAttempt] = useState(0);
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
  const availableTimeframes = state.data?.availableTimeframes ?? [];

  useEffect(() => {
    if (!active || !dfPath || state.data?.dfPath === dfPath) return undefined;
    let mounted = true;
    const controller = new AbortController();
    setState({ data: null, error: "", loading: true });
    Promise.all([loadCsvDataset(dfPath, controller.signal), fetchCachedText(resultPath, controller.signal)])
      .then(([dataset, resultText]) => {
        const newestChunkIndex = dataset.chunks.length - 1;
        const csvText = dataset.chunks[newestChunkIndex] ?? dataset.text;
        const trades = flattenResults(JSON.parse(resultText)).find((result) => result.symbol === symbol)?.trades ?? [];
        if (mounted) {
          pagingRef.current = {
            key: `${dfPath}:${timeframe}`,
            chunks: dataset.chunks,
            nextChunkIndex: newestChunkIndex - 1,
            loading: false,
            exhausted: newestChunkIndex <= 0,
          };
          setState({
            data: { config, csvText, chunks: dataset.chunks, nextChunkIndex: newestChunkIndex - 1, availableTimeframes: availableMarketTimeframes(csvText), trades, dfPath },
            error: "",
            loading: false,
          });
        }
      })
      .catch((error) => {
        if (mounted && error.name !== "AbortError") {
          setState({ data: null, error: `Chart initialization failed: ${error.message ?? String(error)}`, loading: false });
          onChartActivationError?.(symbol);
        }
      });
    return () => { mounted = false; controller.abort(); };
  }, [active, config, dfPath, onChartActivationError, resultPath, retryAttempt, symbol, state.data?.dfPath, timeframe]);

  useEffect(() => {
    const key = `${dfPath}:${timeframe}`;
    pagingKeyRef.current = key;
  }, [dfPath, timeframe]);

  useEffect(() => {
    const options = state.data?.availableTimeframes ?? [];
    if (options.length > 0 && !options.includes(timeframe)) {
      setTimeframe(options.includes(config.entryTf) ? config.entryTf : options[0]);
    }
  }, [config.entryTf, state.data, timeframe]);

  useEffect(() => {
    if (!active || !state.data || !chartData?.records || !containerRef.current) return;

    const chartKey = `${dfPath}:${symbol}:${timeframe}:${isMobile}`;
    if (chartRef.current && chartKeyRef.current !== chartKey) {
      observerRef.current?.disconnect();
      observerRef.current = null;
      if (chartContentRef.current.colorHandler) chartRef.current.events.off("chart:updated", chartContentRef.current.colorHandler);
      chartRef.current.destroy();
      chartRef.current = null;
      loadedChartRecordsRef.current = null;
      chartContentRef.current = { indicators: [], drawingIds: [], colorHandler: null };
    }
    if (chartRef.current) return;

    const chart = new QFChart(containerRef.current, qfChartOptions({ ...state.data.config, symbol }));
    chartRef.current = chart;
    chartKeyRef.current = chartKey;
    chart.registerDrawingRenderer(backtestTradesRenderer);
    chart.registerDrawingRenderer(sessionBoundariesRenderer);
    chart.registerDrawingRenderer(consolidationHotspotsRenderer);
    observerRef.current = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => chart.resize());
    observerRef.current?.observe(containerRef.current);
  }, [active, chartData, dfPath, isMobile, state.data, timeframe, symbol]);

  useEffect(() => {
    const chart = chartRef.current;
    const records = chartData?.records;
    if (!chart || !state.data || !records) return;

    const previousRecords = loadedChartRecordsRef.current;
    const preserveRange = previousRecords && records.length > previousRecords.length
      ? visibleCategoryRange(chart, previousRecords)
      : null;
    chart.setMarketData(records);
    loadedChartRecordsRef.current = records;
    if (preserveRange) {
      chart.getChart().dispatchAction?.({ type: "dataZoom", startValue: preserveRange.start, endValue: preserveRange.end });
    }

    for (const item of chartContentRef.current.indicators) {
      if (item.kind === "indicator") chart.removeIndicator(item.id);
    }
    for (const drawingId of chartContentRef.current.drawingIds) chart.removeDrawing(drawingId);

    const items = buildIndicatorItems(records, state.data.config, timeframe);
    setIndicatorItems(items);
    for (const item of items) {
      if (indicatorVisibility[item.visibilityKey] === false || item.kind !== "indicator") continue;
      chart.addIndicator(item.built.id, item.built.plots, chartAddOptions(item.built.addOptions));
    }
    const patches = indicatorSeriesColorPatches(items.filter((item) => item.kind === "indicator").map((item) => item.built));
    if (chartContentRef.current.colorHandler) chart.events.off("chart:updated", chartContentRef.current.colorHandler);
    const syncColors = () => applyIndicatorSeriesColors(chart, patches);
    chartContentRef.current.colorHandler = syncColors;
    syncColors();
    chart.events.on("chart:updated", syncColors);

    const tradesDrawing = buildBacktestTradesDrawing(records, state.data.trades);
    const sessionBoundariesDrawing = buildSessionBoundariesDrawing(records);
    // QFChart batches drawings into one custom series; add the largest first so
    // trailing markers remain inside the custom-series dimensions.
    const visibleDrawings = items
      .filter((item) => item.kind === "drawing" && indicatorVisibility[item.visibilityKey] !== false)
      .map((item) => item.drawing);
    const drawings = [sessionBoundariesVisible ? sessionBoundariesDrawing : null, tradesDrawing, ...visibleDrawings]
      .filter(Boolean)
      .sort((left, right) => right.points.length - left.points.length);
    for (const drawing of drawings) chart.addDrawing(drawing);
    chartContentRef.current.indicators = items;
    chartContentRef.current.drawingIds = drawings.map(({ id }) => id);
  }, [chartData, state.data]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!active || !chart || !state.data || !chartData?.records) return undefined;
    const visibleIndicators = indicatorItems
      .filter((item) => indicatorVisibility[item.visibilityKey] !== false)
      .map((item) => item.entry);
    const updatePriceScale = () => applyVisiblePriceScale(chart, chartData.records, visibleIndicators);
    const loadOlderWhenNeeded = () => {
      const paging = pagingRef.current;
      const key = `${dfPath}:${timeframe}`;
      if (!state.data.chunks || paging.exhausted || paging.loading || pagingKeyRef.current !== key) return;
      if (!isNearLoadedLeftEdge(chart, chartData.records.length)) return;
      const chunkIndex = paging.nextChunkIndex;
      if (chunkIndex === null || chunkIndex < 0 || chunkIndex >= state.data.chunks.length) {
        paging.exhausted = true;
        return;
      }
      paging.key = key;
      paging.loading = true;
      try {
        const olderCsv = state.data.chunks[chunkIndex];
        if (!olderCsv?.trim()) {
          paging.exhausted = true;
          return;
        }
        const mergedCsv = prependCsvChunk(olderCsv, state.data.csvText);
        paging.nextChunkIndex = chunkIndex - 1;
        paging.exhausted = paging.nextChunkIndex < 0;
        setState((previous) => previous.data?.dfPath === dfPath
          ? { ...previous, data: { ...previous.data, csvText: mergedCsv, nextChunkIndex: paging.nextChunkIndex }, error: "" }
          : previous);
      } catch (error) {
        setState((previous) => ({ ...previous, error: `Unable to load older candles: ${error.message ?? String(error)}` }));
      } finally {
        paging.loading = false;
      }
    };
    const handleDataZoom = () => {
      updatePriceScale();
      loadOlderWhenNeeded();
    };
    updatePriceScale();
    chart.events.on("chart:dataZoom", handleDataZoom);
    return () => chart.events.off("chart:dataZoom", handleDataZoom);
  }, [active, chartData, dfPath, indicatorItems, indicatorVisibility, isMobile, state.data, timeframe]);

  useEffect(() => () => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (chartContentRef.current.colorHandler) chartRef.current?.events.off("chart:updated", chartContentRef.current.colorHandler);
    chartRef.current?.destroy();
    chartRef.current = null;
    chartKeyRef.current = null;
    loadedChartRecordsRef.current = null;
  }, []);

  useEffect(() => {
    if (!active || !chartRef.current || !state.data || !chartData?.records) return undefined;
    const chart = chartRef.current;
    chart.resize();
    const frame = requestAnimationFrame(() => onChartActivationReady?.(symbol));
    return () => cancelAnimationFrame(frame);
  }, [active, chartData, onChartActivationReady, state.data, symbol]);

  useEffect(() => {
    if (!active || !state.data) return;
    if (chartData?.error || availableTimeframes.length === 0) onChartActivationError?.(symbol);
  }, [active, availableTimeframes.length, chartData, onChartActivationError, state.data, symbol]);

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

  const displayError = state.error || chartData?.error || (state.data && availableTimeframes.length === 0
    ? "Chart data has no timeframe with complete OHLC columns."
    : "");
  const showSkeleton = !state.data && !state.error && (state.loading || active);
  return (
    <div hidden={!visible} className={`relative ${visible ? "flex" : "hidden"} h-full min-h-0 w-full flex-col overflow-hidden`}>
      {showSkeleton ? <MarketChartSkeleton
        symbol={symbol}
        symbols={symbols}
        pendingSymbol={pendingSymbol}
        symbolMenuOpen={symbolMenuOpen}
        onSymbolMenuOpenChange={onSymbolMenuOpenChange}
        onSymbolChange={onSymbolChange}
      /> : <>
          {displayError && <div className="absolute inset-x-4 top-4 z-30"><Alert kind="error" role="alert">{displayError}</Alert></div>}
          {state.error && !state.data && <button type="button" onClick={() => { setState({ data: null, error: "", loading: true }); setRetryAttempt((attempt) => attempt + 1); }} className="absolute right-4 top-4 z-30 min-h-9 rounded-md border border-foreground/15 bg-[#111111] px-3 text-sm font-semibold text-foreground hover:bg-foreground/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f8eff]">Retry</button>}
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
                {symbols.length > 0 && <MarketChartSymbolSelect
                  symbol={symbol}
                  symbols={symbols}
                  pendingSymbol={pendingSymbol}
                  visible={visible}
                  open={symbolMenuOpen}
                  onOpenChange={onSymbolMenuOpenChange}
                  onValueChange={onSymbolChange}
                />}
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
      </>}
    </div>
  );
}
