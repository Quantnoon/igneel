import assert from "node:assert/strict";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, test, vi } from "vitest";

const { chart, chartApi, chartDrawings, zoomHandlers, QFChart } = vi.hoisted(() => {
  const handlers = new Set();
  const drawings = new Map();
  const api = {
    getOption: vi.fn(() => ({
      dataZoom: [{ type: "inside", start: 0, end: 100 }],
      xAxis: [{ data: ["first", "last"] }],
      series: [
        { name: "support-zone::support-zone-low", type: "custom" },
        { name: "support-zone::support-zone-high", type: "custom" },
      ],
    })),
    setOption: vi.fn(),
  };
  const chartHost = {
    addDrawing: vi.fn((drawing) => drawings.set(drawing.id, drawing)),
    addIndicator: vi.fn(),
    destroy: vi.fn(),
    getDrawing: vi.fn((id) => drawings.get(id)),
    removeDrawing: vi.fn((id) => drawings.delete(id)),
    removeIndicator: vi.fn(),
    registerDrawingRenderer: vi.fn(),
    resize: vi.fn(),
    setMarketData: vi.fn(),
    getChart: vi.fn(() => api),
    events: {
      on: vi.fn((event, handler) => { if (event === "chart:dataZoom") handlers.add(handler); }),
      off: vi.fn((event, handler) => { if (event === "chart:dataZoom") handlers.delete(handler); }),
    },
  };
  return {
    chart: chartHost,
    chartApi: api,
    chartDrawings: drawings,
    zoomHandlers: handlers,
    QFChart: vi.fn(function QFChartMock() { return chartHost; }),
  };
});

vi.mock("@qfo/qfchart", () => ({ QFChart }));

import { MarketChartPage, qfChartOptions } from "./MarketChartPage.jsx";
import { CONSOLIDATION_HOTSPOT_DRAWING_ID } from "./lib/consolidation-hotspots.js";
import { SESSION_BOUNDARY_DRAWING_ID } from "./lib/session-boundaries.js";

const config = {
  symbol: "Volatility 25 Index",
  entryTf: "M15",
  indicators: [{ type: "SUPPORT_ZONE", columns: ["support_low_H4", "support_high_H4"] }],
};
const csv = [
  "time,open_M15,high_M15,low_M15,close_M15,volume_M15,support_low_H4,support_high_H4",
  "2023-11-14 22:13:20,100,110,95,105,10,90,96",
  "2023-11-14 22:28:20,105,112,101,108,11,90,96",
].join("\n");
const results = JSON.stringify({
  "Volatility 25 Index": [{ name: "Support Resistance", report: { trade_log: [{ position: "buy", entry: 105, exit: 108, open_time: "2023-11-14T22:13:20Z", close_time: "2023-11-14T22:28:20Z", result: "win" }] } }],
});

class ResizeObserverMock {
  static instances = [];
  constructor(callback) { this.callback = callback; this.disconnect = vi.fn(); ResizeObserverMock.instances.push(this); }
  observe = vi.fn();
}

let mediaMatches = false;
let mediaChangeListener;

beforeEach(() => {
  vi.clearAllMocks();
  chartDrawings.clear();
  zoomHandlers.clear();
  ResizeObserverMock.instances = [];
  globalThis.ResizeObserver = ResizeObserverMock;
  mediaMatches = false;
  mediaChangeListener = undefined;
  globalThis.matchMedia = vi.fn(() => ({
    matches: mediaMatches,
    addEventListener: vi.fn((event, listener) => { if (event === "change") mediaChangeListener = listener; }),
    removeEventListener: vi.fn(),
  }));
  globalThis.fetch = vi.fn((url) => {
    const path = String(url);
    const body = path.startsWith("df") ? csv : results;
    return Promise.resolve({ ok: true, text: () => Promise.resolve(body) });
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("creates a QFChart with market data, filled-zone indicators, and result trade drawings", async () => {
  render(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);

  await waitFor(() => assert.equal(QFChart.mock.calls.length, 1));
  await waitFor(() => assert.equal(chartApi.setOption.mock.calls.length, 3));
  const [, options] = QFChart.mock.calls[0];
  assert.equal(options.backgroundColor, "#0a0a0a");
  assert.equal(options.height, "100%");
  assert.deepEqual(options.dataZoom, { visible: true, position: "top", start: 75, end: 100 });
  assert.equal(chart.setMarketData.mock.calls[0][0].length, 2);
  assert.equal(chart.addIndicator.mock.calls[0][0], "support-zone");
  assert.equal(chart.addIndicator.mock.calls[0][1]["support-zone-fill"].options.style, "fill");
  assert.deepEqual(
    chart.registerDrawingRenderer.mock.calls.map(([renderer]) => renderer.type),
    ["backtest-trades", SESSION_BOUNDARY_DRAWING_ID, CONSOLIDATION_HOTSPOT_DRAWING_ID],
  );
  assert.equal(chart.addDrawing.mock.calls.length, 2);
  assert.equal(new Set(chart.addDrawing.mock.calls.map(([drawing]) => drawing.id)).size, 2);
  const tradeDrawing = chart.addDrawing.mock.calls.map(([drawing]) => drawing).find((drawing) => drawing.id === "backtest-trades");
  assert.equal(tradeDrawing.points.length, 2);
  assert.deepEqual(chartApi.setOption.mock.calls[0][0], {
    series: [
      { name: "support-zone::support-zone-low", type: "custom", color: "#43A047" },
      { name: "support-zone::support-zone-high", type: "custom", color: "#43A047" },
    ],
  });
  assert.deepEqual(chartApi.setOption.mock.calls[2][0], { yAxis: [{ min: 88.9, max: 113.1 }] });
  assert.ok(chart.events.on.mock.calls.some(([event]) => event === "chart:updated"));
  assert.equal(ResizeObserverMock.instances[0].observe.mock.calls.length, 1);

  zoomHandlers.forEach((handler) => handler());
  assert.equal(chartApi.setOption.mock.calls.length, 4);
  assert.deepEqual(chartApi.setOption.mock.calls[3][0], { yAxis: [{ min: 88.9, max: 113.1 }] });
});

test("registers the session-boundary renderer and adds its markers after market data loads", async () => {
  const sessionCsv = [
    "time,open_M15,high_M15,low_M15,close_M15,volume_M15,support_low_H4,support_high_H4",
    "2023-11-14 07:45:00,100,105,99,102,10,90,96",
    "2023-11-14 08:00:00,102,108,101,106,11,90,96",
  ].join("\n");
  globalThis.fetch = vi.fn((url) => {
    const path = String(url);
    const body = path.startsWith("df") ? sessionCsv : "{}";
    return Promise.resolve({ ok: true, text: () => Promise.resolve(body) });
  });

  render(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);

  await waitFor(() => assert.equal(QFChart.mock.calls.length, 1));
  assert.deepEqual(
    chart.registerDrawingRenderer.mock.calls.map(([renderer]) => renderer.type),
    ["backtest-trades", SESSION_BOUNDARY_DRAWING_ID, CONSOLIDATION_HOTSPOT_DRAWING_ID],
  );
  const drawings = chart.addDrawing.mock.calls.map(([drawing]) => drawing);
  assert.equal(drawings.length, 1);
  assert.equal(drawings[0].id, SESSION_BOUNDARY_DRAWING_ID);
  assert.equal(drawings[0].type, SESSION_BOUNDARY_DRAWING_ID);
  assert.deepEqual(drawings[0].points, [{ timeIndex: 1, value: 102, paneIndex: 0 }]);
  assert.deepEqual(drawings[0].colors, ["#42A5F5"]);

  zoomHandlers.forEach((handler) => handler());
  assert.ok(chartApi.setOption.mock.calls.some(([option]) => Array.isArray(option.yAxis)));
});

test("toggles consolidation hotspots without changing session indicators and includes bounds in the price scale", async () => {
  chartApi.getOption.mockReturnValue({
    dataZoom: [{ type: "inside", start: 0, end: 100 }],
    xAxis: [{ data: ["one", "two", "three"] }],
    series: [],
  });
  const hotspotConfig = {
    ...config,
    indicators: [
      {
        type: "CONSOLIDATION_HOTSPOT",
        columns: ["consolidation_H1", "consolidation_id_H1", "consolidation_high_H1", "consolidation_low_H1"],
      },
      { type: "ASIAN_HIGH", columns: ["asian_high_H1"] },
    ],
  };
  const hotspotCsv = [
    "time,open_M15,high_M15,low_M15,close_M15,volume_M15,consolidation_H1,consolidation_id_H1,consolidation_high_H1,consolidation_low_H1,asian_high_H1",
    "2026-08-25 12:00:00+00:00,1.13,1.14,1.12,1.13,10,True,49,1.14154,1.13587,1.139",
    "2026-08-25 12:15:00+00:00,1.13,1.14,1.12,1.13,10,true,49,1.14154,1.13587,1.139",
    "2026-08-25 12:30:00+00:00,1.13,1.14,1.12,1.13,10,false,,,,1.139",
  ].join("\n");
  globalThis.fetch = vi.fn((url) => Promise.resolve({
    ok: true,
    text: () => Promise.resolve(String(url).startsWith("df") ? hotspotCsv : "{}"),
  }));

  render(<MarketChartPage active config={hotspotConfig} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);

  await waitFor(() => assert.equal(QFChart.mock.calls.length, 1));
  const drawing = chart.addDrawing.mock.calls.map(([entry]) => entry).find((entry) => entry.id === CONSOLIDATION_HOTSPOT_DRAWING_ID);
  assert.ok(drawing);
  assert.equal(chart.addDrawing.mock.calls.filter(([entry]) => entry.id === CONSOLIDATION_HOTSPOT_DRAWING_ID).length, 1, "the hotspot is registered exactly once");
  assert.deepEqual(drawing.points, [
    { timeIndex: -0.5, value: 1.14154, paneIndex: 0 },
    { timeIndex: 1.5, value: 1.13587, paneIndex: 0 },
  ]);
  assert.ok(chartApi.setOption.mock.calls.some(([option]) => option.yAxis?.[0]?.max > 1.14154));
  assert.equal(chart.addIndicator.mock.calls.length, 1, "the session level is initially plotted");

  const hotspotToggle = screen.getByRole("button", { name: /Consolidation Hotspot/ });
  fireEvent.click(hotspotToggle);
  assert.equal(hotspotToggle.getAttribute("aria-pressed"), "false");
  assert.equal(chart.removeDrawing.mock.calls.at(-1)[0], CONSOLIDATION_HOTSPOT_DRAWING_ID);
  assert.equal(chartDrawings.has(CONSOLIDATION_HOTSPOT_DRAWING_ID), false, "one click removes the hotspot drawing");
  assert.equal(chart.removeIndicator.mock.calls.length, 0);
  assert.equal(chart.addIndicator.mock.calls.length, 1, "hiding the hotspot leaves session indicators untouched");

  fireEvent.click(hotspotToggle);
  assert.equal(hotspotToggle.getAttribute("aria-pressed"), "true");
  assert.equal(chart.addDrawing.mock.calls.at(-1)[0].id, CONSOLIDATION_HOTSPOT_DRAWING_ID);
  assert.equal(chartDrawings.has(CONSOLIDATION_HOTSPOT_DRAWING_ID), true, "one click restores the hotspot drawing");
  assert.equal(chart.addDrawing.mock.calls.filter(([entry]) => entry.id === CONSOLIDATION_HOTSPOT_DRAWING_ID).length, 2);
  assert.equal(chart.addIndicator.mock.calls.length, 1, "restoring the hotspot leaves session indicators untouched");
});

test("initializes only when active, reflows after showing, and destroys on unmount", async () => {
  const view = render(<MarketChartPage active={false} config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);
  assert.equal(QFChart.mock.calls.length, 0);

  view.rerender(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);
  await waitFor(() => assert.equal(QFChart.mock.calls.length, 1));
  const resizeBeforeHide = chart.resize.mock.calls.length;
  view.rerender(<MarketChartPage active={false} config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);
  assert.equal(chart.destroy.mock.calls.length, 0);
  view.rerender(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);
  await waitFor(() => assert.ok(chart.resize.mock.calls.length > resizeBeforeHide));

  view.unmount();
  assert.equal(chart.destroy.mock.calls.length, 1);
  assert.equal(ResizeObserverMock.instances[0].disconnect.mock.calls.length, 1);
});

test("builds the Quantnoon QFChart theme without the built-in databox", () => {
  const options = qfChartOptions({ symbol: "XAUUSD", entryTf: "H4" });
  assert.equal(options.title, "XAUUSD");
  assert.equal(options.upColor, "#22c55e");
  assert.equal(options.downColor, "#ef4444");
  assert.equal(options.databox, undefined);
});

test("uses a compact text result button with the primary-blue icon", async () => {
  render(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" onViewBacktestResults={() => {}} />);
  const button = screen.getByRole("button", { name: "View Backtest Results" });
  assert.match(button.className, /text-foreground/);
  assert.doesNotMatch(button.className, /bg-\[#0f8eff\]/);
  assert.match(button.querySelector("svg").getAttribute("class"), /text-\[#0f8eff\]/);
});

test("uses the responsive indicator overlay on mobile without restoring the databox", async () => {
  render(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);
  await waitFor(() => assert.equal(QFChart.mock.calls.length, 1));
  assert.equal(QFChart.mock.calls[0][1].databox, undefined);

  mediaChangeListener({ matches: true });

  await waitFor(() => assert.equal(QFChart.mock.calls.length, 2));
  assert.equal(chart.destroy.mock.calls.length, 1);
  assert.equal(QFChart.mock.calls[1][1].databox, undefined);
  const toggle = screen.getByRole("button", { name: "Indicators" });
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  fireEvent.click(toggle);
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
});

test("toggles a rendered indicator by crossing out its accessible button", async () => {
  const user = userEvent.setup();
  render(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);
  const indicator = await screen.findByRole("button", { name: /Support Zone/ });
  assert.equal(indicator.getAttribute("aria-pressed"), "true");
  assert.equal(screen.queryByRole("checkbox"), null);

  await user.click(indicator);
  assert.equal(chart.removeIndicator.mock.calls[0][0], "support-zone");
  assert.equal(indicator.getAttribute("aria-pressed"), "false");
  assert.match(indicator.textContent, /Support Zone/);
  assert.ok(indicator.querySelector("span.line-through"));

  await user.keyboard("{Enter}");
  assert.equal(chart.addIndicator.mock.calls.length, 2);
  assert.equal(indicator.getAttribute("aria-pressed"), "true");
  assert.equal(indicator.querySelector("span.line-through"), null);
});

test("toggles fixed UTC session boundaries through its crossed-out button", async () => {
  render(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);
  const toggle = await screen.findByRole("button", { name: "Session Boundaries" });
  await waitFor(() => assert.equal(QFChart.mock.calls.length, 1));
  assert.equal(toggle.getAttribute("aria-pressed"), "true");

  fireEvent.click(toggle);
  assert.ok(chart.removeDrawing.mock.calls.some(([id]) => id === SESSION_BOUNDARY_DRAWING_ID));
  assert.equal(toggle.getAttribute("aria-pressed"), "false");
  assert.ok(toggle.querySelector("span.line-through"));

  fireEvent.click(toggle);
  assert.ok(chart.addDrawing.mock.calls.some(([drawing]) => drawing.id === SESSION_BOUNDARY_DRAWING_ID));
  assert.equal(toggle.getAttribute("aria-pressed"), "true");
  assert.equal(toggle.querySelector("span.line-through"), null);
});

test("switches timeframe using that timeframe's OHLC columns and keeps indicator visibility", async () => {
  const timeframeCsv = [
    "time,open_M15,high_M15,low_M15,close_M15,volume_M15,open_H1,high_H1,low_H1,close_H1,volume_H1,support_low_H4,support_high_H4",
    "2026-08-25 12:00:00+00:00,1,2,0.5,1.5,10,1,3,0.25,2,40,0.8,1",
    "2026-08-25 12:15:00+00:00,1.5,2.5,1,2,11,1,3,0.25,2,40,0.8,1",
  ].join("\n");
  globalThis.fetch = vi.fn((url) => Promise.resolve({
    ok: true,
    text: () => Promise.resolve(String(url).startsWith("df") ? timeframeCsv : results),
  }));
  render(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);
  const indicator = await screen.findByRole("button", { name: /Support Zone/ });
  fireEvent.click(indicator);
  assert.equal(indicator.getAttribute("aria-pressed"), "false");

  fireEvent.click(screen.getByRole("button", { name: "H1" }));
  await waitFor(() => assert.equal(chart.setMarketData.mock.calls.length, 2));
  const h1Records = chart.setMarketData.mock.calls[1][0];
  assert.equal(h1Records.length, 1);
  assert.deepEqual(
    { open: h1Records[0].open, high: h1Records[0].high, low: h1Records[0].low, close: h1Records[0].close },
    { open: 1, high: 3, low: 0.25, close: 2 },
  );
  assert.equal(chart.addIndicator.mock.calls.length, 1, "hidden indicator remains hidden after timeframe change");
  const h1Indicator = screen.getByRole("button", { name: /Support Zone/ });
  assert.equal(h1Indicator.getAttribute("aria-pressed"), "false");
  assert.ok(h1Indicator.querySelector("span.line-through"));
});

test("keeps a configured indicator hidden when its chart runtime ID changes by timeframe", async () => {
  const twoIndicatorConfig = {
    ...config,
    indicators: [
      { type: "LONDON_HIGH", columns: ["london_high_M15"] },
      { type: "LONDON_HIGH", columns: ["london_high_H1"] },
    ],
  };
  const csvWithRuntimeIdShift = [
    "time,open_M15,high_M15,low_M15,close_M15,volume_M15,open_H1,high_H1,low_H1,close_H1,volume_H1,london_high_M15,london_high_H1",
    "2026-08-25 12:00:00+00:00,1,2,0.5,1.5,10,1,3,0.25,2,40,,5",
    "2026-08-25 12:15:00+00:00,,,,,10,1,3,0.25,2,40,4,6",
  ].join("\n");
  globalThis.fetch = vi.fn((url) => Promise.resolve({
    ok: true,
    text: () => Promise.resolve(String(url).startsWith("df") ? csvWithRuntimeIdShift : results),
  }));
  render(<MarketChartPage active config={twoIndicatorConfig} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);

  const hiddenAcrossTimeframes = await screen.findByRole("button", { name: /London High · H1/ });
  assert.equal(hiddenAcrossTimeframes.getAttribute("aria-pressed"), "true");
  fireEvent.click(hiddenAcrossTimeframes);
  assert.equal(chart.removeIndicator.mock.calls[0][0], "london-high");

  fireEvent.click(screen.getByRole("button", { name: "H1" }));
  await waitFor(() => assert.equal(chart.setMarketData.mock.calls.length, 2));
  const h1HiddenIndicator = screen.getByRole("button", { name: /London High · H1/ });
  assert.equal(h1HiddenIndicator.getAttribute("aria-pressed"), "false");
  assert.ok(h1HiddenIndicator.querySelector("span.line-through"));
  assert.equal(chart.addIndicator.mock.calls.some(([id]) => id === "london-high_H1"), false);

  fireEvent.click(h1HiddenIndicator);
  assert.equal(chart.addIndicator.mock.calls.at(-1)[0], "london-high_H1");
  assert.equal(h1HiddenIndicator.getAttribute("aria-pressed"), "true");
});

test("chart symbol selector calls the shared workspace selection callback", async () => {
  const user = userEvent.setup();
  const onSymbolChange = vi.fn();
  const onViewBacktestResults = vi.fn();
  render(<MarketChartPage
    active
    config={config}
    symbol="Volatility 25 Index"
    symbols={["Volatility 25 Index", "EURUSD"]}
    onSymbolChange={onSymbolChange}
    onViewBacktestResults={onViewBacktestResults}
    dfPath="df.csv"
    resultPath="result.json"
  />);

  const selector = screen.getByRole("combobox", { name: "Chart symbol" });
  assert.match(selector.textContent, /Volatility 25 Index/);
  await waitFor(() => screen.getByRole("button", { name: "M15" }));
  assert.match(screen.getByRole("button", { name: "M15" }).className, /bg-\[#0f8eff\]\/15/);
  const resultsButton = screen.getByRole("button", { name: /View Backtest Results/ });
  assert.doesNotMatch(resultsButton.className, /bg-\[#0f8eff\]/);
  assert.match(resultsButton.querySelector("svg").getAttribute("class"), /text-\[#0f8eff\]/);
  await user.click(resultsButton);
  assert.equal(onViewBacktestResults.mock.calls.length, 1);
  await user.click(selector);
  await user.click(await screen.findByRole("option", { name: "EURUSD" }));
  assert.equal(onSymbolChange.mock.calls[0][0], "EURUSD");
});
