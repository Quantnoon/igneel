import assert from "node:assert/strict";
import { afterEach, test, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

const chartSpies = vi.hoisted(() => ({
  chart: vi.fn(() => ({ update: vi.fn(), reflow: vi.fn(), destroy: vi.fn() })),
  stockChart: vi.fn(() => ({ update: vi.fn(), reflow: vi.fn(), destroy: vi.fn() })),
}));

vi.mock("highcharts/highstock", () => ({ default: chartSpies }));

import { HighchartsChart } from "./HighchartsChart.jsx";

afterEach(() => {
  cleanup();
  chartSpies.chart.mockClear();
  chartSpies.stockChart.mockClear();
  vi.unstubAllGlobals();
});

test("creates a normal Highcharts chart for analytics", () => {
  vi.stubGlobal("requestAnimationFrame", (callback) => { callback(); return 1; });
  render(<HighchartsChart options={{ series: [] }} />);
  assert.equal(chartSpies.chart.mock.calls.length, 1);
  assert.equal(chartSpies.stockChart.mock.calls.length, 0);
});

test("creates a Highstock chart for the market workspace", () => {
  vi.stubGlobal("requestAnimationFrame", (callback) => { callback(); return 1; });
  render(<HighchartsChart stock options={{ series: [] }} />);
  assert.equal(chartSpies.stockChart.mock.calls.length, 1);
  assert.equal(chartSpies.chart.mock.calls.length, 0);
});
