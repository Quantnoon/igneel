import assert from "node:assert/strict";
import { test } from "vitest";

import {
  CONSOLIDATION_HOTSPOT_COLOR,
  CONSOLIDATION_HOTSPOT_DRAWING_ID,
  CONSOLIDATION_HOTSPOT_FILL,
  buildConsolidationHotspotsDrawing,
  consolidationHotspots,
  consolidationHotspotsRenderer,
} from "./consolidation-hotspots.js";

const indicators = [{
  type: "CONSOLIDATION_HOTSPOT",
  columns: ["consolidation_H1", "consolidation_id_H1", "consolidation_high_H1", "consolidation_low_H1"],
}];

function row(active, id = 49, high = 1.14154, low = 1.13587) {
  return {
    consolidation_H1: active,
    consolidation_id_H1: id,
    consolidation_high_H1: high,
    consolidation_low_H1: low,
  };
}

test("groups contiguous active rows by ID and splits inactive, changed, or invalid rows", () => {
  const records = [
    row(true),
    row(true),
    row(false),
    row(true, 50, 1.15, 1.14),
    row(true, 51, 1.16, 1.15),
    row(true, 52, 1.17, 1.18),
    row(true, 53, Number.NaN, 1.1),
  ];

  assert.deepEqual(consolidationHotspots(records, indicators), [
    { id: 49, high: 1.14154, low: 1.13587, startIndex: 0, endIndex: 1 },
    { id: 50, high: 1.15, low: 1.14, startIndex: 3, endIndex: 3 },
    { id: 51, high: 1.16, low: 1.15, startIndex: 4, endIndex: 4 },
  ]);
});

test("returns no hotspots when configuration or active consolidation data is absent", () => {
  assert.deepEqual(consolidationHotspots([row(true)], []), []);
  assert.deepEqual(consolidationHotspots([{}], indicators), []);
  assert.equal(buildConsolidationHotspotsDrawing([row(false)], indicators), null);
});

test("builds two chart points per hotspot, extending across the active candles", () => {
  const drawing = buildConsolidationHotspotsDrawing([row(true), row(true), row(false), row(true, 50, 2, 1)], indicators);

  assert.equal(drawing.id, CONSOLIDATION_HOTSPOT_DRAWING_ID);
  assert.equal(drawing.type, CONSOLIDATION_HOTSPOT_DRAWING_ID);
  assert.deepEqual(drawing.points, [
    { timeIndex: -0.5, value: 1.14154, paneIndex: 0 },
    { timeIndex: 1.5, value: 1.13587, paneIndex: 0 },
    { timeIndex: 2.5, value: 2, paneIndex: 0 },
    { timeIndex: 3.5, value: 1, paneIndex: 0 },
  ]);
});

test("renderer draws one silent burnt-orange rectangle per valid point pair", () => {
  const element = consolidationHotspotsRenderer.render({
    pixelPoints: [[20, 80], [60, 40], [100, 30], [140, 50], [null, 2]],
  });

  assert.equal(consolidationHotspotsRenderer.type, CONSOLIDATION_HOTSPOT_DRAWING_ID);
  assert.equal(CONSOLIDATION_HOTSPOT_COLOR, "#F97316");
  assert.equal(CONSOLIDATION_HOTSPOT_FILL, "rgba(249, 115, 22, 0.18)");
  assert.equal(element.type, "group");
  assert.equal(element.silent, true);
  assert.deepEqual(element.children, [
    {
      type: "rect",
      shape: { x: 20, y: 40, width: 40, height: 40 },
      style: { fill: CONSOLIDATION_HOTSPOT_FILL, stroke: CONSOLIDATION_HOTSPOT_COLOR, lineWidth: 1 },
      silent: true,
    },
    {
      type: "rect",
      shape: { x: 100, y: 30, width: 40, height: 20 },
      style: { fill: CONSOLIDATION_HOTSPOT_FILL, stroke: CONSOLIDATION_HOTSPOT_COLOR, lineWidth: 1 },
      silent: true,
    },
  ]);
});
