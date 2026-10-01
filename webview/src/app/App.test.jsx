import assert from "node:assert/strict";
import { afterEach, beforeEach, test, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router";

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
  botUrls: {
    windows: "https://example.com/support-resistance-windows.ex5",
    mac: "https://example.com/support-resistance-mac.ex5",
  },
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
function renderApp() { return render(<BrowserRouter><App /></BrowserRouter>); }

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url) => String(url).startsWith("strategies/strategies.json")
    ? response(JSON.stringify(MANIFEST))
    : response(JSON.stringify(CONFIG))));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); setUrl("/"); });

test("lists new strategy identities at their short routes", async () => {
  setUrl("/");
  renderApp();
  const card = await screen.findByRole("link", { name: /support_resistance/ });
  assert.equal(card.getAttribute("href"), "/support_resistance");
});

test("matches strategy routes, reports unknown routes, and supports browser back navigation", async () => {
  const user = userEvent.setup();
  setUrl("/");
  renderApp();
  await user.click(await screen.findByRole("link", { name: /support_resistance/ }));
  await screen.findByTestId("market-chart");
  assert.equal(window.location.pathname, "/support_resistance");

  window.history.back();
  await screen.findByRole("heading", { name: "Strategies" });
  assert.equal(window.location.pathname, "/");
});

test("renders not-found pages for an unknown strategy and a nested unknown path", async () => {
  setUrl("/missing_strategy");
  const strategyRoute = renderApp();
  assert.match((await screen.findByRole("heading", { name: "Strategy not found" })).textContent, /Strategy not found/);
  assert.match(screen.getByText(/No strategy named/).textContent, /missing_strategy/);

  strategyRoute.unmount();
  setUrl("/unknown/nested");
  renderApp();
  await screen.findByRole("heading", { name: "Strategy not found" });
  assert.match(screen.getByText(/No strategy named/).textContent, /unknown\/nested/);
});

test("uses chart and results navigation with strategy topbar controls", async () => {
  const user = userEvent.setup();
  setUrl("/support_resistance");
  renderApp();
  await screen.findByTestId("market-chart");
  assert.equal(screen.getByTestId("market-chart").textContent, "Chart active EURUSDm strategies/support_resistance/EURUSDm_df.csv");
  assert.equal(screen.queryByRole("tab"), null);
  assert.equal(screen.queryByLabelText("Symbol"), null);
  const header = screen.getByRole("banner");
  const headerLayout = header.firstElementChild;
  assert.match(headerLayout.className, /grid-cols-\[1fr_auto_1fr\]/);
  assert.equal(headerLayout.children[1], header.querySelector("h1"));
  assert.equal(screen.getByRole("link", { name: "Back to strategies" }).getAttribute("href"), "/");
  const download = screen.getByRole("button", { name: "Download bot" });
  await user.click(download);
  const windowsOption = await screen.findByRole("menuitem", { name: "Windows" });
  const macOption = screen.getByRole("menuitem", { name: "MacBook" });
  assert.match(windowsOption.parentElement.className, /grid-cols-2/);
  assert.equal(windowsOption.getAttribute("href"), "https://example.com/support-resistance-windows.ex5");
  assert.equal(macOption.getAttribute("href"), "https://example.com/support-resistance-mac.ex5");
  assert.ok(windowsOption.hasAttribute("download"));
  assert.ok(macOption.hasAttribute("download"));
  assert.ok(windowsOption.querySelector('[data-testid="windows-icon"]'));
  assert.ok(macOption.querySelector('[data-testid="apple-icon"]'));

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

test("restores the active workspace tab when browser back and forward changes the hash", async () => {
  const user = userEvent.setup();
  setUrl("/support_resistance#chart");
  renderApp();
  await screen.findByTestId("market-chart");

  await user.click(screen.getByRole("button", { name: "View Backtest Results" }));
  await screen.findByTestId("backtest-results");
  assert.equal(window.location.hash, "#results");

  window.history.back();
  await waitFor(() => assert.match(screen.getByTestId("market-chart").textContent, /Chart active/));
  assert.equal(window.location.hash, "#chart");

  window.history.forward();
  await waitFor(() => assert.match(screen.getByTestId("backtest-results").textContent, /Results active/));
  assert.equal(window.location.hash, "#results");
});

test("keeps the chart toolbar symbol selector connected to workspace state", async () => {
  const user = userEvent.setup();
  setUrl("/support_resistance");
  renderApp();
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
  renderApp();
  const header = await screen.findByRole("banner");
  assert.match(header.querySelector("h1").className, /text-center/);
  assert.match(header.firstElementChild.className, /grid-cols-\[1fr_auto_1fr\]/);
  assert.doesNotMatch(header.firstElementChild.className, /min-h-20/);
});

test("keeps the platform menu available and disables options without URLs", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn(async (url) => String(url).startsWith("strategies/strategies.json")
    ? response(JSON.stringify([{ ...MANIFEST[0], botUrls: { mac: MANIFEST[0].botUrls.mac } }]))
    : response(JSON.stringify(CONFIG))));
  setUrl("/support_resistance");
  renderApp();
  await screen.findByTestId("market-chart");
  await user.click(screen.getByRole("button", { name: "Download bot" }));
  const windowsOption = await screen.findByRole("menuitem", { name: "Windows" });
  const macOption = screen.getByRole("menuitem", { name: "MacBook" });
  assert.equal(windowsOption.getAttribute("aria-disabled"), "true");
  assert.equal(windowsOption.hasAttribute("href"), false);
  assert.equal(macOption.getAttribute("href"), MANIFEST[0].botUrls.mac);
});

test("opens the platform menu with both options disabled when no URLs are available", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn(async (url) => String(url).startsWith("strategies/strategies.json")
    ? response(JSON.stringify([{ ...MANIFEST[0], botUrls: undefined }]))
    : response(JSON.stringify(CONFIG))));
  setUrl("/support_resistance");
  renderApp();
  await screen.findByTestId("market-chart");
  const trigger = screen.getByRole("button", { name: "Download bot" });
  assert.equal(trigger.disabled, false);
  await user.click(trigger);
  assert.equal((await screen.findByRole("menuitem", { name: "Windows" })).getAttribute("aria-disabled"), "true");
  assert.equal(screen.getByRole("menuitem", { name: "MacBook" }).getAttribute("aria-disabled"), "true");
});

test("reports malformed strategy configuration", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url) => String(url).startsWith("strategies/strategies.json")
    ? response(JSON.stringify(MANIFEST)) : response('{ nope')));
  setUrl("/support_resistance");
  renderApp();
  const alert = await screen.findByRole("alert");
  assert.match(alert.textContent, /config.json is not valid JSON/);
});
