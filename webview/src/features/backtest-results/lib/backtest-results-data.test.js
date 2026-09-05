import assert from "node:assert/strict";
import { test } from "vitest";

import {
  breakdownRows,
  buildBalanceSeries,
  buildDrawdownSeries,
  chronologicalTrades,
  filterAndSortTrades,
  flattenResults,
  orderedTradeColumns,
  parseFormattedNumber,
} from "./backtest-results-data.js";

test("flattens per-symbol result objects while retaining report trades", () => {
  const results = flattenResults({
    GBPUSD: { name: "one", report: { trade_log: [{ result: "win" }] } },
    EURUSD: { name: "three", report: { trade_log: [] } },
  });

  assert.deepEqual(results.map(({ symbol, name, trades }) => [symbol, name, trades.length]), [
    ["GBPUSD", "one", 1],
    ["EURUSD", "three", 0],
  ]);
  assert.throws(() => flattenResults([]), /keyed by symbol/);
});

test("orders known trade columns first and preserves future columns", () => {
  const columns = orderedTradeColumns([{ extra: 1, result: "win", position: "buy" }, { another: 2 }]);
  assert.deepEqual(columns, ["position", "result", "extra", "another"]);
});

test("sorts trades chronologically and preserves source order for equal or invalid times", () => {
  const trades = [
    { id: "late", close_time: "2026-01-02T00:00:00Z" },
    { id: "first tie", close_time: "2026-01-01T00:00:00Z" },
    { id: "second tie", close_time: "2026-01-01T00:00:00Z" },
    { id: "invalid", close_time: null },
  ];
  assert.deepEqual(chronologicalTrades(trades).map((trade) => trade.id), ["first tie", "second tie", "late", "invalid"]);
});

test("builds USD balance growth from stored balances including skipped flat points", () => {
  const report = { currency: "USD", starting_balance: "$100.00", final_balance: "$105.00" };
  const trades = [
    { close_time: "2026-01-02", balance_after: 105, pnl_dollar: 5, result: "win" },
    { close_time: "2026-01-01", balance_after: 100, pnl_dollar: 0, skipped: true },
  ];
  const balance = buildBalanceSeries(report, trades);

  assert.deepEqual(balance.points.map((point) => point.y), [100, 100, 105]);
  assert.equal(balance.points[1].trade.skipped, true);
  assert.equal(balance.reconciles, true);
});

test("builds converted balance growth from cumulative pnl_currency", () => {
  const report = { currency: "NGN", starting_balance: "₦145,000.00", final_balance: "₦147,900.00" };
  const balance = buildBalanceSeries(report, [
    { close_time: "2026-01-01", balance_after: 101, pnl_currency: 1450, result: "win" },
    { close_time: "2026-01-02", balance_after: 102, pnl_currency: 1450, result: "win" },
  ]);

  assert.deepEqual(balance.points.map((point) => point.y), [145000, 146450, 147900]);
  assert.equal(balance.reconciles, true);
});

test("derives drawdown from the exact balance series", () => {
  const drawdown = buildDrawdownSeries([{ x: 0, y: 100 }, { x: 1, y: 120 }, { x: 2, y: 90 }, { x: 3, y: 108 }]);
  assert.deepEqual(drawdown.map((point) => point.y), [0, 0, -25, -10]);
});

test("orders breakdowns and supports trade search and stable sorting", () => {
  assert.deepEqual(
    breakdownRows({ Friday: {}, Monday: {}, Wednesday: {} }, ["Monday", "Wednesday", "Friday"]).map(([name]) => name),
    ["Monday", "Wednesday", "Friday"],
  );
  const trades = [{ position: "sell", pnl: -2 }, { position: "buy", pnl: 10 }, { position: "buy", pnl: 2 }];
  assert.deepEqual(filterAndSortTrades(trades, ["position", "pnl"], "buy", "pnl", "desc").map((trade) => trade.pnl), [10, 2]);
});

test("parses formatted currencies, percentages, and non-finite strings", () => {
  assert.equal(parseFormattedNumber("$1,234.50"), 1234.5);
  assert.equal(parseFormattedNumber("13.37%"), 13.37);
  assert.equal(parseFormattedNumber("Infinity"), Number.POSITIVE_INFINITY);
  assert.equal(parseFormattedNumber(null), null);
});
