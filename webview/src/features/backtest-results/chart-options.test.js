import assert from "node:assert/strict";
import { test } from "vitest";

import { buildBalanceChart } from "./chart-options.js";

test("builds account balance growth as a gradient area series", () => {
  const { balance, options } = buildBalanceChart(
    { currency: "USD", starting_balance: "$100.00", final_balance: "$105.00" },
    [{ close_time: "2026-08-01T01:00:00Z", balance_after: 105, pnl_dollar: 5, result: "win" }],
  );

  assert.equal(options.series[0].type, "area");
  assert.equal(options.series[0].threshold, null);
  assert.equal(options.series[0].fillColor.stops.length, 2);
  assert.equal(options.series[0].data, balance.points);
  assert.equal(options.series[0].data[1].trade.result, "win");
});
