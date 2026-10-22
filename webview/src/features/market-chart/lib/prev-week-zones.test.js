import assert from "node:assert/strict";
import { test } from "vitest";

import {
  PREV_WEEK_LEVEL_LINE_DASH,
  PREV_WEEK_ZONES_COLOR,
  PREV_WEEK_ZONES_DRAWING_ID,
  buildPrevWeekZonesDrawing,
  prevWeekZonesRenderer,
} from "./prev-week-zones.js";

const WEEK_COLUMNS = [
  "prev_week_zone1_low_H1",
  "prev_week_zone1_high_H1",
  "prev_week_zone1_type_H1",
  "prev_week_zone1_source_H1",
  "prev_week_zone2_low_H1",
  "prev_week_zone2_high_H1",
  "prev_week_zone2_type_H1",
  "prev_week_zone2_source_H1",
  "prev_week_zone3_low_H1",
  "prev_week_zone3_high_H1",
  "prev_week_zone3_type_H1",
  "prev_week_zone3_source_H1",
  "prev_week_zone4_low_H1",
  "prev_week_zone4_high_H1",
  "prev_week_zone4_type_H1",
  "prev_week_zone4_source_H1",
  "prev_week_zone5_low_H1",
  "prev_week_zone5_high_H1",
  "prev_week_zone5_type_H1",
  "prev_week_zone5_source_H1",
  "prev_week_high_level_H1",
  "prev_week_low_level_H1",
  "prev_week_atr_H1",
];

function config(columns = WEEK_COLUMNS) {
  return [{ type: "PREV_WEEK_ZONES", columns }];
}

function weekOneBar(time, slot, { low, high, type, source }) {
  return {
    time,
    [`prev_week_zone${slot}_low_H1`]: low,
    [`prev_week_zone${slot}_high_H1`]: high,
    [`prev_week_zone${slot}_type_H1`]: type,
    [`prev_week_zone${slot}_source_H1`]: source,
  };
}

function weekLevels(time, { high, low, atr }) {
  return {
    time,
    prev_week_high_level_H1: high,
    prev_week_low_level_H1: low,
    prev_week_atr_H1: atr,
  };
}

function twoWeekRecords() {
  const weekOne = { high: 15, low: 9, atr: 2 };
  const weekTwo = { high: 25, low: 19, atr: 2 };
  return [
    { time: Date.UTC(2026, 0, 5) },
    { time: Date.UTC(2026, 0, 6) },
    { time: Date.UTC(2026, 0, 7) },
    weekOneBar(Date.UTC(2026, 0, 12), 1, { low: 10, high: 12, type: "support", source: "PWL" }),
    weekOneBar(Date.UTC(2026, 0, 13), 1, { low: 10, high: 12, type: "support", source: "PWL" }),
    weekOneBar(Date.UTC(2026, 0, 14), 1, { low: 10, high: 12, type: "support", source: "PWL" }),
    weekOneBar(Date.UTC(2026, 0, 19), 1, { low: 20, high: 22, type: "resistance", source: "PWH" }),
    weekOneBar(Date.UTC(2026, 0, 20), 1, { low: 20, high: 22, type: "resistance", source: "PWH" }),
    weekOneBar(Date.UTC(2026, 0, 21), 1, { low: 20, high: 22, type: "resistance", source: "PWH" }),
  ].map((record, index) => {
    if (index >= 3 && index <= 5) return { ...record, ...weekLevels(record.time, weekOne) };
    if (index >= 6) return { ...record, ...weekLevels(record.time, weekTwo) };
    return record;
  });
}

test("draws merged zones across the current week", () => {
  const drawing = buildPrevWeekZonesDrawing(twoWeekRecords(), config());

  assert.ok(drawing);
  assert.equal(drawing.id, PREV_WEEK_ZONES_DRAWING_ID);
  assert.equal(drawing.type, PREV_WEEK_ZONES_DRAWING_ID);
  assert.deepEqual(drawing.rectStyles, [
    { fill: "rgba(44, 160, 44, 0.18)", stroke: "#2ca02c" },
    { fill: "rgba(214, 39, 40, 0.18)", stroke: "#d62728" },
  ]);

  // Bands cover only the bars where the zone values exist; the lookback
  // week is never painted.
  assert.deepEqual(drawing.points.slice(0, 4), [
    { timeIndex: 2.5, value: 12, paneIndex: 0 },
    { timeIndex: 5.5, value: 10, paneIndex: 0 },
    { timeIndex: 5.5, value: 22, paneIndex: 0 },
    { timeIndex: 8.5, value: 20, paneIndex: 0 },
  ]);
});

test("draws dashed PWH/PWL levels across the current week", () => {
  const drawing = buildPrevWeekZonesDrawing(twoWeekRecords(), config());

  assert.deepEqual(drawing.lineStyles, Array(4).fill({ color: PREV_WEEK_ZONES_COLOR }));
  assert.deepEqual(drawing.points.slice(4, 12), [
    { timeIndex: 2.5, value: 15, paneIndex: 0 },
    { timeIndex: 5.5, value: 15, paneIndex: 0 },
    { timeIndex: 5.5, value: 25, paneIndex: 0 },
    { timeIndex: 8.5, value: 25, paneIndex: 0 },
    { timeIndex: 2.5, value: 9, paneIndex: 0 },
    { timeIndex: 5.5, value: 9, paneIndex: 0 },
    { timeIndex: 5.5, value: 19, paneIndex: 0 },
    { timeIndex: 8.5, value: 19, paneIndex: 0 },
  ]);
});

test("labels zones with R/S/N ranks and shortens long sources", () => {
  const records = [
    { time: Date.UTC(2026, 0, 5) },
    { time: Date.UTC(2026, 0, 12) },
  ];
  const bars = [
    weekOneBar(records[1].time, 1, { low: 99.9, high: 100.1, type: "neutral", source: "PWO" }),
    weekOneBar(records[1].time, 2, { low: 100.4, high: 100.6, type: "neutral", source: "MID" }),
    weekOneBar(records[1].time, 3, { low: 104.9, high: 105.1, type: "resistance", source: "PWH" }),
    weekOneBar(records[1].time, 4, { low: 89.9, high: 90.1, type: "support", source: "PWL" }),
    weekOneBar(records[1].time, 5, { low: 94.9, high: 95.1, type: "support", source: "PWL+PWO+MID" }),
  ];
  records[1] = { ...bars[0], ...bars[1], ...bars[2], ...bars[3], ...bars[4], prev_week_atr_H1: 2 };

  const drawing = buildPrevWeekZonesDrawing(records, config());
  const zoneLabels = drawing.labels.filter((label) => label.align === "right");

  // Ascending level order: S2 at 90, S1 at 95, N1 at 100; the second
  // neutral zone (100.5) is suppressed by the 0.75 * ATR spacing rule.
  assert.deepEqual(zoneLabels.map((label) => label.text), [
    "S2 PWL ",
    "S1 PWL+2 ",
    "N1 PWO ",
    "R1 PWH ",
  ]);
});

test("renderer emits rect, line and text children from the drawing", () => {
  const drawing = buildPrevWeekZonesDrawing(twoWeekRecords(), config());
  const pixelPoints = drawing.points.map((point, index) => [index * 10, point.value]);
  const rendered = prevWeekZonesRenderer.render({ drawing, pixelPoints });

  assert.equal(rendered.type, "group");
  assert.equal(rendered.children.length, 12);

  const rects = rendered.children.filter((child) => child.type === "rect");
  assert.equal(rects.length, 2);
  assert.equal(rects[0].style.stroke, "#2ca02c");
  assert.equal(rects[1].style.stroke, "#d62728");

  const lines = rendered.children.filter((child) => child.type === "line");
  assert.equal(lines.length, 4);
  assert.deepEqual(lines[0].style.lineDash, PREV_WEEK_LEVEL_LINE_DASH);

  const texts = rendered.children.filter((child) => child.type === "text");
  assert.deepEqual(texts.map((child) => child.style.text), [
    " PWH",
    " PWH",
    " PWL",
    " PWL",
    "S1 PWL ",
    "R1 PWH ",
  ]);
  assert.equal(texts[4].style.align, "right");
  assert.equal(texts[4].style.verticalAlign, "middle");
});

test("returns null without usable zone columns or data", () => {
  assert.equal(buildPrevWeekZonesDrawing([], config()), null);
  assert.equal(buildPrevWeekZonesDrawing(twoWeekRecords(), []), null);
  assert.equal(
    buildPrevWeekZonesDrawing(twoWeekRecords(), config(["prev_week_zone1_low_H1"])),
    null,
  );
  assert.equal(
    buildPrevWeekZonesDrawing([{ time: Date.UTC(2026, 0, 5) }], config()),
    null,
  );
});
