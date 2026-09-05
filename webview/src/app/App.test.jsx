import assert from "node:assert/strict";
import { afterEach, beforeEach, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../features/market-chart/MarketChartPage.jsx", () => ({
  MarketChartPage: ({ active, dfPath, symbol }) => <div data-testid="market-chart">{`Chart ${active ? "active" : "inactive"} ${symbol} ${dfPath}`}</div>,
}));
vi.mock("../features/backtest-results/BacktestResultsPage.jsx", () => ({
  BacktestResultsPage: ({ active, dfPath, symbol }) => <div data-testid="backtest-results">{`Results ${active ? "active" : "inactive"} ${symbol} ${dfPath}`}</div>,
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

test("uses the workspace selector to switch both tabs to the selected symbol", async () => {
  const user = userEvent.setup();
  setUrl("/support_resistance");
  render(<App />);
  await screen.findByTestId("market-chart");
  assert.equal(screen.getByTestId("market-chart").textContent, "Chart active EURUSDm strategies/support_resistance/EURUSDm_df.csv");

  screen.getByLabelText("Symbol").focus();
  fireEvent.keyDown(screen.getByLabelText("Symbol"), { key: "ArrowDown" });
  await user.click(await screen.findByRole("option", { name: "GBPUSDm" }));
  await waitFor(() => assert.equal(screen.getByTestId("market-chart").textContent, "Chart active GBPUSDm strategies/support_resistance/GBPUSDm_df.csv"));

  fireEvent.click(screen.getByRole("tab", { name: "Backtest Results" }));
  assert.equal(screen.getByTestId("backtest-results").textContent, "Results active GBPUSDm strategies/support_resistance/GBPUSDm_df.csv");
});

test("reports malformed strategy configuration", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url) => String(url).startsWith("strategies/strategies.json")
    ? response(JSON.stringify(MANIFEST)) : response('{ nope')));
  setUrl("/support_resistance");
  render(<App />);
  const alert = await screen.findByRole("alert");
  assert.match(alert.textContent, /config.json is not valid JSON/);
});
