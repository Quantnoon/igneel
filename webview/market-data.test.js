import assert from "node:assert/strict";
import test from "node:test";

import {
  collapseEntryCandles,
  convertMarketData,
  interpolateIndicatorPoints,
  parseCsv,
  rawIndicatorPoints,
  toEpochMilliseconds,
} from "./market-data.js";

const HEADER = "time,open_M15,high_M15,low_M15,close_M15,volume_M15";
const INDICATOR_HEADER = `${HEADER},ema_12_H1,sma_50_H1`;

test("parses quoted fields, escaped quotes, and CRLF rows", () => {
  assert.deepEqual(parseCsv('name,value\r\n"a,b","a""b"\r\n'), [
    ["name", "value"],
    ["a,b", 'a"b'],
  ]);
});

test("normalizes naive and timezone-aware timestamps to UTC", () => {
  const expected = Date.UTC(2026, 7, 25, 14, 30);
  assert.equal(toEpochMilliseconds("2026-08-25 14:30:00", 2), expected);
  assert.equal(toEpochMilliseconds("2026-08-25T16:30:00+02:00", 2), expected);
});

test("converts finite candle values and skips missing OHLCV rows", () => {
  const csv = [
    HEADER,
    '"2026-08-25 12:00:00+00:00",1,2,0.5,1.5,10',
    "2026-08-25 12:15:00+00:00,2,3,1.5,,20",
  ].join("\n");

  assert.deepEqual(convertMarketData(csv, "M15"), [
    { time: Date.UTC(2026, 7, 25, 12), open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
  ]);
});

test("reports missing columns and malformed required values", () => {
  assert.throws(() => convertMarketData("time,close_M15\n2026-08-25,1", "M15"), /open_M15/);
  assert.throws(
    () => convertMarketData(`${HEADER}\n2026-08-25,1,Infinity,0.5,1.5,10`, "M15"),
    /high_M15 is not a finite number/,
  );
});

test("rejects empty usable datasets and malformed CSV", () => {
  assert.throws(() => convertMarketData(`${HEADER}\n2026-08-25,1,2,,1.5,10`, "M15"), /No usable/);
  assert.throws(() => parseCsv('name\n"unfinished'), /unterminated/);
});

test("attaches finite indicator values and skips empty or NaN cells", () => {
  const csv = [
    INDICATOR_HEADER,
    '"2026-08-25 12:00:00+00:00",1,2,0.5,1.5,10,1.25,2.5',
    '"2026-08-25 12:15:00+00:00",2,3,1.5,2.5,20,,NaN',
    '"2026-08-25 12:30:00+00:00",3,4,2.5,3.5,30,3.25,',
  ].join("\n");

  assert.deepEqual(convertMarketData(csv, "M15", ["ema_12_H1", "sma_50_H1"]), [
    { time: Date.UTC(2026, 7, 25, 12), open: 1, high: 2, low: 0.5, close: 1.5, volume: 10, ema_12_H1: 1.25, sma_50_H1: 2.5 },
    { time: Date.UTC(2026, 7, 25, 12, 15), open: 2, high: 3, low: 1.5, close: 2.5, volume: 20 },
    { time: Date.UTC(2026, 7, 25, 12, 30), open: 3, high: 4, low: 2.5, close: 3.5, volume: 30, ema_12_H1: 3.25 },
  ]);
});

test("tolerates missing indicator columns while keeping OHLCV required", () => {
  const csv = `${INDICATOR_HEADER}\n"2026-08-25 12:00:00+00:00",1,2,0.5,1.5,10,1.25,2.5`;

  const records = convertMarketData(csv, "M15", ["ema_12_H1", "missing_H1"]);
  assert.deepEqual(records, [
    { time: Date.UTC(2026, 7, 25, 12), open: 1, high: 2, low: 0.5, close: 1.5, volume: 10, ema_12_H1: 1.25 },
  ]);
  assert.throws(() => convertMarketData("time,close_M15,ema_12_H1\n2026-08-25,1,2", "M15", ["ema_12_H1"]), /open_M15/);
});

test("collapses repeated entry timeframe candles into one candle", () => {
  const csv = [
    HEADER.replaceAll("_M15", "_H1"),
    '"2026-08-25 12:00:00+00:00",1,2,0.5,1.5,10',
    '"2026-08-25 12:15:00+00:00",1,2,0.5,1.5,10',
    '"2026-08-25 12:30:00+00:00",1,2,0.5,1.5,10',
    '"2026-08-25 12:45:00+00:00",1,2,0.5,1.5,10',
    '"2026-08-25 13:00:00+00:00",2,3,1.5,2.5,20',
    '"2026-08-25 13:15:00+00:00",2,3,1.5,2.5,20',
  ].join("\n");

  const records = convertMarketData(csv, "H1");
  assert.deepEqual(records, [
    { time: Date.UTC(2026, 7, 25, 12), open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    { time: Date.UTC(2026, 7, 25, 13), open: 2, high: 3, low: 1.5, close: 2.5, volume: 20 },
  ]);
});

test("keeps distinct entry timeframe candles with equal OHLCV runs intact", () => {
  const records = collapseEntryCandles([
    { time: 0, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    { time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    { time: 2, open: 1, high: 2, low: 0.5, close: 1.5, volume: 20 },
    { time: 3, open: 1, high: 2, low: 0.5, close: 1.5, volume: 20 },
    { time: 4, open: 3, high: 4, low: 2.5, close: 3.5, volume: 30 },
  ]);
  assert.deepEqual(records.map((record) => record.time), [0, 2, 4]);
});

test("collapseEntryCandles returns empty and single-record inputs unchanged", () => {
  assert.deepEqual(collapseEntryCandles([]), []);
  const single = [{ time: 0, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }];
  assert.deepEqual(collapseEntryCandles(single), single);
});

function candleRecord(time, indicatorValues = {}) {
  return { time, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10, ...indicatorValues };
}

test("interpolates higher timeframe values between update anchors", () => {
  const records = [
    candleRecord(0),
    candleRecord(1, { ema_12_H1: 1 }),
    candleRecord(2, { ema_12_H1: 1 }),
    candleRecord(3, { ema_12_H1: 1 }),
    candleRecord(4, { ema_12_H1: 3 }),
    candleRecord(5, { ema_12_H1: 3 }),
  ];

  const points = interpolateIndicatorPoints(records, "ema_12_H1", "M15");
  assert.deepEqual(points.map((point) => point.time), [1, 2, 3, 4, 5]);
  assert.equal(points[0].value, 1);
  assert.ok(Math.abs(points[1].value - 5 / 3) < 1e-9);
  assert.ok(Math.abs(points[2].value - 7 / 3) < 1e-9);
  assert.equal(points[3].value, 3);
  assert.equal(points[4].value, 3);
});

test("extracts raw zone points without interpolating changes", () => {
  const records = [
    candleRecord(0),
    candleRecord(1, { supply_low_H1: 10 }),
    candleRecord(2, { supply_low_H1: 10 }),
    candleRecord(3, { supply_low_H1: Number.POSITIVE_INFINITY }),
    candleRecord(4, { supply_low_H1: 14 }),
    candleRecord(5, { supply_low_H1: 14 }),
  ];

  assert.deepEqual(rawIndicatorPoints(records, "supply_low_H1"), [
    { time: 1, value: 10 },
    { time: 2, value: 10 },
    { time: 4, value: 14 },
    { time: 5, value: 14 },
  ]);
  assert.deepEqual(rawIndicatorPoints(records, "missing_H1"), []);
});

test("keeps native timeframe and unsuffixed columns uninterpolated", () => {
  const records = [
    candleRecord(0, { sma_12_M15: 1 }),
    candleRecord(1, { sma_12_M15: 1 }),
    candleRecord(2, { sma_12_M15: 5 }),
    candleRecord(3, { ema_12: 2 }),
    candleRecord(4, { ema_12: 2 }),
  ];

  assert.deepEqual(interpolateIndicatorPoints(records, "sma_12_M15", "M15"), [
    { time: 0, value: 1 },
    { time: 1, value: 1 },
    { time: 2, value: 5 },
  ]);
  assert.deepEqual(interpolateIndicatorPoints(records, "ema_12", "M15"), [
    { time: 3, value: 2 },
    { time: 4, value: 2 },
  ]);
});

test("interpolation preserves warmup gaps, empty columns, and flat series", () => {
  const records = [
    candleRecord(0),
    candleRecord(1),
    candleRecord(2, { ema_12_H1: 4 }),
    candleRecord(3, { ema_12_H1: 4 }),
    candleRecord(4, { ema_12_H1: 4 }),
  ];

  assert.deepEqual(interpolateIndicatorPoints(records, "ema_12_H1", "M15"), [
    { time: 2, value: 4 },
    { time: 3, value: 4 },
    { time: 4, value: 4 },
  ]);
  assert.deepEqual(interpolateIndicatorPoints(records, "missing_H1", "M15"), []);
  assert.deepEqual(interpolateIndicatorPoints([], "ema_12_H1", "M15"), []);
});
