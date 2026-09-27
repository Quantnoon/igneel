import assert from "node:assert/strict";
import { afterEach, beforeEach, test, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../features/market-chart/MarketChartPage.jsx", () => ({
  MarketChartPage: ({ active, dfPath, symbol, symbols, onSymbolChange, onViewBacktestResults }) => (
    <div>
      <div data-testid="market-chart">{`Chart ${active ? "active" : "inactive"} ${symbol} ${dfPath}`}</div>
      <button type="button" onClick={() => onSymbolChange?.("GBPUSDm")}>Chart select GBPUSDm</button>
      <button type="button" onClick={onViewBacktestResults}>View Backtest Results</button>
      <span data-testid="chart-symbols">{symbols?.join(",")}</span>
    </div>
  ),
}));
vi.mock("../features/backtest-results/BacktestResultsPage.jsx", () => ({
  BacktestResultsPage: ({ active, dfPath, symbol, symbols, onSymbolChange, onBackToChart }) => (
    <div>
      <div data-testid="backtest-results">{`Results ${active ? "active" : "inactive"} ${symbol} ${dfPath}`}</div>
      <span data-testid="results-symbols">{symbols?.join(",")}</span>
      <button type="button" onClick={() => onSymbolChange?.("EURUSDm")}>Results select EURUSDm</button>
      <button type="button" onClick={onBackToChart}>Back to Chart</button>
    </div>
  ),
}));

import { App } from "./App.jsx";

const MANIFEST = [{
  name: "strategies/support_resistance",
  env: { development: {
    df: [
      { name: "EURUSDm", path: "strategies/support_resistance/EURUSDm_df.csv" },
      { name: "GBPUSDm", path: "strategies/support_resistance/GBPUSDm_df.csv" },
    ],
    config: "strategies/support_resistance/config.json",
    result: "strategies/support_resistance/result.json",
  }, production: { df: [], config: "", result: "" } },
}];
const CONFIG = { symbols: ["EURUSDm", "GBPUSDm"], entry_tf: "M15", indicators: [] };

function response(text) { return { ok: true, status: 200, text: async () => text }; }
function setUrl(url) { window.history.replaceState(null, "", url); }

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url) => String(url).startsWith("strategies/strategies.json")
    ? response(JSON.stringify(MANIFEST))
    : response(JSON.stringify(CONFIG))));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); setUrl("/"); });

test("lists new strategy identities at their short routes", async () => {
  setUrl("/");
  render(<App />);
  const card = await screen.findByRole("link", { name: /support_resistance/ });
  assert.equal(card.getAttribute("href"), "/support_resistance");
});

test("uses chart and results buttons for two-way navigation without top controls", async () => {
  const user = userEvent.setup();
  setUrl("/support_resistance");
  render(<App />);
  await screen.findByTestId("market-chart");
  assert.equal(screen.getByTestId("market-chart").textContent, "Chart active EURUSDm strategies/support_resistance/EURUSDm_df.csv");
  assert.equal(screen.queryByRole("tab"), null);
  assert.equal(screen.queryByLabelText("Symbol"), null);

  await user.click(screen.getByRole("button", { name: "Chart select GBPUSDm" }));
  await waitFor(() => assert.equal(screen.getByTestId("market-chart").textContent, "Chart active GBPUSDm strategies/support_resistance/GBPUSDm_df.csv"));

  await user.click(screen.getByRole("button", { name: "View Backtest Results" }));
  assert.equal(screen.getByTestId("backtest-results").textContent, "Results active GBPUSDm strategies/support_resistance/GBPUSDm_df.csv");
  assert.equal(screen.getByTestId("results-symbols").textContent, "EURUSDm,GBPUSDm");
  assert.equal(window.location.hash, "#results");

  await user.click(screen.getByRole("button", { name: "Results select EURUSDm" }));
  await waitFor(() => assert.equal(screen.getByTestId("backtest-results").textContent, "Results active EURUSDm strategies/support_resistance/EURUSDm_df.csv"));

  await user.click(screen.getByRole("button", { name: "Back to Chart" }));
  assert.equal(screen.getByTestId("market-chart").textContent, "Chart active EURUSDm strategies/support_resistance/EURUSDm_df.csv");
  assert.equal(window.location.hash, "#chart");
});

test("keeps the chart toolbar symbol selector connected to workspace state", async () => {
  const user = userEvent.setup();
  setUrl("/support_resistance");
  render(<App />);
  await screen.findByTestId("market-chart");
  assert.equal(screen.getByTestId("chart-symbols").textContent, "EURUSDm,GBPUSDm");

  await user.click(screen.getByRole("button", { name: "Chart select GBPUSDm" }));
  await waitFor(() => {
    assert.match(screen.getByTestId("market-chart").textContent, /GBPUSDm/);
    assert.equal(screen.getByTestId("chart-symbols").textContent, "EURUSDm,GBPUSDm");
  });
});

test("centers powered-by branding in the app header", async () => {
  setUrl("/");
  render(<App />);
  const header = await screen.findByRole("banner");
  assert.match(header.querySelector("h1").className, /text-center/);
  assert.match(header.firstElementChild.className, /justify-center/);
  assert.doesNotMatch(header.firstElementChild.className, /min-h-20/);
});

test("reports malformed strategy configuration", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url) => String(url).startsWith("strategies/strategies.json")
    ? response(JSON.stringify(MANIFEST)) : response('{ nope')));
  setUrl("/support_resistance");
  render(<App />);
  const alert = await screen.findByRole("alert");
  assert.match(alert.textContent, /config.json is not valid JSON/);
});
