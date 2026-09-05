import assert from "node:assert/strict";
import { afterEach, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("../../shared/components/HighchartsChart.jsx", () => ({
  HighchartsChart: ({ options, children, ...props }) => <div {...props} data-testid="highchart" data-title={options.title?.text}>{children}</div>,
}));

import { BacktestResultsPage } from "./BacktestResultsPage.jsx";

const report = {
  currency: "USD", starting_balance: 100, final_balance: 110, peak_balance: 110,
  total_return_pct: "10%", max_drawdown_pct: "1%", trades_taken: 1, trades_skipped: 0,
  win_rate_pct: "100%", profit_factor: 1, sharpe_ratio: 0, sortino_ratio: 0,
  avg_win: 10, avg_loss: 0, gross_profit: 10, gross_loss: 0,
  day_breakdown: {}, session_breakdown: {}, skip_breakdown: {},
  trade_log: [{ position: "buy", entry: 1, exit: 2, open_time: "2026-08-01T00:00:00Z", close_time: "2026-08-01T01:00:00Z", result: "win", pnl_dollar: 10, balance_after: 110 }],
};
const payload = { EURUSDm: { name: "support_resistance", report } };
const csv = "time,close_M15\n2026-08-01 00:00:00+00:00,1";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("renders only the workspace-selected symbol from a result-object payload", async () => {
  vi.stubGlobal("requestAnimationFrame", (callback) => { callback(); return 1; });
  vi.stubGlobal("fetch", vi.fn(async (url) => ({ ok: true, status: 200, text: async () => String(url).startsWith("df") ? csv : JSON.stringify(payload) })));
  render(<BacktestResultsPage active symbol="EURUSDm" resultPath="result.json" dfPath="df.csv" />);
  assert.ok(await screen.findByText(/EURUSDm.*support_resistance/));
  assert.equal(screen.queryByLabelText("Symbol"), null);
  assert.equal(screen.queryByLabelText("Strategy"), null);
});

test("explains when the selected symbol has no result", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, text: async () => JSON.stringify(payload) })));
  render(<BacktestResultsPage active symbol="GBPUSDm" resultPath="result.json" dfPath="df.csv" />);
  assert.ok(await screen.findByText(/No backtest results are available for GBPUSDm/));
});
