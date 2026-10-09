import assert from "node:assert/strict";
import { test } from "vitest";

import { priceLevelColumns, priceZoneColumns, visiblePriceRange, visibleRecordIndexes } from "./visible-price-range.js";

const records = [
  { low: 10, high: 12, support_low_H4: 9, support_high_H4: 10 },
  { low: 11, high: 13, support_low_H4: 10, support_high_H4: 11 },
  { low: 20, high: 22, support_low_H4: 19, support_high_H4: 20 },
  { low: 21, high: 23, support_low_H4: 20, support_high_H4: 21 },
];

test("maps a padded chart viewport to visible record indexes", () => {
  assert.deepEqual(visibleRecordIndexes(4, 6, 16.67, 83.34), { start: 0, end: 3 });
  assert.deepEqual(visibleRecordIndexes(4, 6, 50, 100), { start: 2, end: 3 });
});

test("fits only visible candles and zone bounds with a five-percent buffer", () => {
  const range = visiblePriceRange(records, ["support_low_H4", "support_high_H4"], {
    categoryCount: 6,
    start: 50,
    end: 100,
  });
  assert.deepEqual(range.indexes, { start: 2, end: 3 });
  assert.equal(range.min, 18.8);
  assert.equal(range.max, 23.2);
});

test("uses only configured price-zone indicator columns", () => {
  assert.deepEqual(priceZoneColumns([
    { type: "EMA", columns: ["ema_20_H4"] },
    { type: "RESISTANCE_ZONE", columns: ["resistance_low_H4", "resistance_high_H4"] },
  ]), ["resistance_low_H4", "resistance_high_H4"]);
});

test("includes session levels when expanding the visible price scale", () => {
  const sessionRecords = records.map((record, index) => ({
    ...record,
    london_high_H4: index === 2 ? 30 : undefined,
    london_low_H4: index === 2 ? 29 : undefined,
  }));
  assert.deepEqual(priceLevelColumns([
    { type: "LONDON_HIGH", columns: ["london_high_H4"] },
    { type: "LONDON_LOW", columns: ["london_low_H4"] },
  ]), ["london_high_H4", "london_low_H4"]);
  const range = visiblePriceRange(sessionRecords, priceLevelColumns([
    { type: "LONDON_HIGH", columns: ["london_high_H4"] },
    { type: "LONDON_LOW", columns: ["london_low_H4"] },
  ]), { categoryCount: 4, start: 0, end: 100 });
  assert.equal(range.max, 31);
  assert.equal(range.min, 9);
});

test("includes consolidation bounds but excludes consolidation IDs from the visible price scale", () => {
  const consolidationRecords = [{
    low: 10,
    high: 12,
    consolidation_H1: true,
    consolidation_id_H1: 900,
    consolidation_high_H1: 13,
    consolidation_low_H1: 9,
  }];
  const indicators = [{
    type: "CONSOLIDATION_HOTSPOT",
    columns: ["consolidation_H1", "consolidation_id_H1", "consolidation_high_H1", "consolidation_low_H1"],
  }];
  assert.deepEqual(priceLevelColumns(indicators), ["consolidation_high_H1", "consolidation_low_H1"]);
  const range = visiblePriceRange(consolidationRecords, priceLevelColumns(indicators), {
    categoryCount: 1,
    start: 0,
    end: 100,
  });
  assert.equal(range.max, 13.2);
  assert.equal(range.min, 8.8);
});
