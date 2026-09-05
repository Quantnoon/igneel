import assert from "node:assert/strict";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, test, vi } from "vitest";

const { chart, chartApi, zoomHandlers, QFChart } = vi.hoisted(() => {
  const handlers = new Set();
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
    addDrawing: vi.fn(),
    addIndicator: vi.fn(),
    destroy: vi.fn(),
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
    zoomHandlers: handlers,
    QFChart: vi.fn(function QFChartMock() { return chartHost; }),
  };
});

vi.mock("@qfo/qfchart", () => ({ QFChart }));

import { MarketChartPage, qfChartOptions } from "./MarketChartPage.jsx";
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
  const [, options] = QFChart.mock.calls[0];
  assert.equal(options.backgroundColor, "#0a0a0a");
  assert.equal(options.height, "100%");
  assert.deepEqual(options.dataZoom, { visible: true, position: "top", start: 75, end: 100 });
  assert.equal(chart.setMarketData.mock.calls[0][0].length, 2);
  assert.equal(chart.addIndicator.mock.calls[0][0], "support-zone");
  assert.equal(chart.addIndicator.mock.calls[0][1]["support-zone-fill"].options.style, "fill");
  assert.deepEqual(
    chart.registerDrawingRenderer.mock.calls.map(([renderer]) => renderer.type),
    ["backtest-trades", SESSION_BOUNDARY_DRAWING_ID],
  );
  assert.equal(chart.addDrawing.mock.calls.length, 1);
  assert.equal(chart.addDrawing.mock.calls[0][0].points.length, 2);
  assert.deepEqual(chartApi.setOption.mock.calls[0][0], {
    series: [
      { name: "support-zone::support-zone-low", type: "custom", color: "#43A047" },
      { name: "support-zone::support-zone-high", type: "custom", color: "#43A047" },
    ],
  });
  assert.deepEqual(chartApi.setOption.mock.calls[1][0], { yAxis: [{ min: 88.9, max: 113.1 }] });
  assert.ok(chart.events.on.mock.calls.some(([event]) => event === "chart:updated"));
  assert.equal(ResizeObserverMock.instances[0].observe.mock.calls.length, 1);

  zoomHandlers.forEach((handler) => handler());
  assert.equal(chartApi.setOption.mock.calls.length, 3);
  assert.deepEqual(chartApi.setOption.mock.calls[2][0], { yAxis: [{ min: 88.9, max: 113.1 }] });
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
    ["backtest-trades", SESSION_BOUNDARY_DRAWING_ID],
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

test("builds the Quantnoon QFChart theme", () => {
  const options = qfChartOptions({ symbol: "XAUUSD", entryTf: "H4" });
  assert.equal(options.title, "XAUUSD H4");
  assert.equal(options.upColor, "#22c55e");
  assert.equal(options.downColor, "#ef4444");
  assert.equal(options.databox.position, "right");
  assert.equal(options.databox.triggerOn, "mousemove");
});

test("recreates the chart with a floating tap databox when the viewport becomes mobile", async () => {
  render(<MarketChartPage active config={config} symbol="Volatility 25 Index" dfPath="df.csv" resultPath="result.json" />);
  await waitFor(() => assert.equal(QFChart.mock.calls.length, 1));
  assert.equal(QFChart.mock.calls[0][1].databox.position, "right");

  mediaChangeListener({ matches: true });

  await waitFor(() => assert.equal(QFChart.mock.calls.length, 2));
  assert.equal(chart.destroy.mock.calls.length, 1);
  assert.deepEqual(QFChart.mock.calls[1][1].databox, { position: "floating", triggerOn: "click" });
});
