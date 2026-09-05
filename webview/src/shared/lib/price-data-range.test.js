import assert from "node:assert/strict";
import { test } from "vitest";

import { extractPriceDataRange, formatUtcDate } from "./price-data-range.js";

test("extracts the earliest and latest price timestamps from unsorted CSV rows", () => {
  const range = extractPriceDataRange([
    "time,close_M15",
    "2026-08-31 23:45:00+00:00,3",
    "not-a-date,2",
    "2026-08-01 00:00:00+00:00,1",
    "2026-08-15T12:00:00+02:00,2",
  ].join("\n"));

  assert.deepEqual(range, {
    start: Date.UTC(2026, 7, 1),
    end: Date.UTC(2026, 7, 31, 23, 45),
    elapsedDays: 30,
  });
});

test("returns null for missing, empty, or entirely invalid time data", () => {
  assert.equal(extractPriceDataRange(""), null);
  assert.equal(extractPriceDataRange("close_M15\n1"), null);
  assert.equal(extractPriceDataRange("time,close_M15\ninvalid,1\n,2"), null);
});

test("reports a same-day range and formats dates in UTC", () => {
  const range = extractPriceDataRange("time\n2026-08-25T23:30:00-02:00\n2026-08-26T20:00:00Z");
  assert.equal(range.elapsedDays, 0);
  assert.equal(formatUtcDate(range.start), formatUtcDate(range.end));
});
