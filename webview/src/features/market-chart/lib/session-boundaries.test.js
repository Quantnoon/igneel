import assert from "node:assert/strict";
import { test } from "vitest";

import {
  SESSION_BOUNDARY_DRAWING_ID,
  SESSION_BOUNDARY_LINE_COLOR,
  SESSION_BOUNDARY_LINE_DASH,
  SESSION_BOUNDARY_LINE_WIDTH,
  SESSION_ZONE_COLORS,
  buildSessionBoundariesDrawing,
  sessionBoundariesRenderer,
  sessionBoundaryMarkers,
} from "./session-boundaries.js";

const HOUR = 60 * 60 * 1000;

function candle(time, open = 100, high = 102, low = 99, close = 101) {
  return { time, open, high, low, close, volume: 10 };
}

function seriesOf(startTime, count, interval = HOUR) {
  return Array.from({ length: count }, (_, index) => candle(startTime + index * interval));
}

test("derives colored UTC boundary markers for every loaded trading day", () => {
  const start = Date.UTC(2023, 10, 13);
  const markers = sessionBoundaryMarkers(seriesOf(start, 48));

  assert.equal(markers.length, 12);
  assert.equal(markers[0].time, Date.UTC(2023, 10, 13, 0));
  assert.equal(markers[markers.length - 1].time, Date.UTC(2023, 10, 14, 22));

  assert.deepEqual(
    markers.map((marker) => marker.color),
    [
      SESSION_ZONE_COLORS.asia,
      SESSION_ZONE_COLORS.london,
      SESSION_ZONE_COLORS.asia,
      SESSION_ZONE_COLORS["new-york"],
      SESSION_ZONE_COLORS.london,
      SESSION_ZONE_COLORS["new-york"],
      SESSION_ZONE_COLORS.asia,
      SESSION_ZONE_COLORS.london,
      SESSION_ZONE_COLORS.asia,
      SESSION_ZONE_COLORS["new-york"],
      SESSION_ZONE_COLORS.london,
      SESSION_ZONE_COLORS["new-york"],
    ],
  );
});

test("colors each boundary line with its session-zone color", () => {
  const start = Date.UTC(2023, 10, 13);
  const markers = sessionBoundaryMarkers(seriesOf(start, 24));

  assert.equal(markers.find((marker) => marker.time === Date.UTC(2023, 10, 13, 0)).color, SESSION_ZONE_COLORS.asia);
  assert.equal(markers.find((marker) => marker.time === Date.UTC(2023, 10, 13, 8)).color, SESSION_ZONE_COLORS.london);
  assert.equal(markers.find((marker) => marker.time === Date.UTC(2023, 10, 13, 9)).color, SESSION_ZONE_COLORS.asia);
  assert.equal(markers.find((marker) => marker.time === Date.UTC(2023, 10, 13, 13)).color, SESSION_ZONE_COLORS["new-york"]);
  assert.equal(markers.find((marker) => marker.time === Date.UTC(2023, 10, 13, 17)).color, SESSION_ZONE_COLORS.london);
  assert.equal(markers.find((marker) => marker.time === Date.UTC(2023, 10, 13, 22)).color, SESSION_ZONE_COLORS["new-york"]);
});

test("anchors aligned boundaries to the candle index and positions intra-candle boundaries fractionally", () => {
  const h4Times = [0, 4, 8, 12, 16, 20].map((hour) => Date.UTC(2023, 10, 14, hour));
  const records = [
    ...h4Times.map((time, index) => candle(time, 100 + index, 102 + index, 99 + index, 101 + index)),
    candle(Date.UTC(2023, 10, 15, 0), 107, 109, 106, 108),
  ];
  const markers = sessionBoundaryMarkers(records);

  const aligned = markers.find((marker) => marker.time === Date.UTC(2023, 10, 14, 0));
  assert.equal(aligned.timeIndex, 0);

  const londonStart = markers.find((marker) => marker.time === Date.UTC(2023, 10, 14, 8));
  assert.equal(londonStart.timeIndex, 2);
  assert.equal(londonStart.value, 102);

  const asiaEnd = markers.find((marker) => marker.time === Date.UTC(2023, 10, 14, 9));
  assert.ok(Math.abs(asiaEnd.timeIndex - 2.25) < 1e-9);
  assert.equal(asiaEnd.value, 102);

  const newYorkStart = markers.find((marker) => marker.time === Date.UTC(2023, 10, 14, 13));
  assert.ok(Math.abs(newYorkStart.timeIndex - 3.25) < 1e-9);

  const newYorkEnd = markers.find((marker) => marker.time === Date.UTC(2023, 10, 14, 22));
  assert.ok(Math.abs(newYorkEnd.timeIndex - 5.5) < 1e-9);
});

test("omits boundaries outside the loaded data range", () => {
  const records = seriesOf(Date.UTC(2023, 10, 14, 9, 30), 8 * 60 + 1, 60 * 1000);
  const markers = sessionBoundaryMarkers(records);
  assert.deepEqual(markers.map((marker) => marker.time), [Date.UTC(2023, 10, 14, 13), Date.UTC(2023, 10, 14, 17)]);
});

test("returns no markers for empty or malformed records", () => {
  assert.deepEqual(sessionBoundaryMarkers([]), []);
  assert.deepEqual(sessionBoundaryMarkers(undefined), []);
  assert.deepEqual(sessionBoundaryMarkers([null, {}, { time: Number.NaN }]), []);
  assert.deepEqual(sessionBoundaryMarkers([{ time: "not-a-time" }]), []);
  assert.equal(buildSessionBoundariesDrawing([]), null);
});

test("builds one batched drawing with a point and color per marker", () => {
  const records = seriesOf(Date.UTC(2023, 10, 14), 24);
  const drawing = buildSessionBoundariesDrawing(records);

  assert.ok(drawing);
  assert.equal(drawing.id, SESSION_BOUNDARY_DRAWING_ID);
  assert.equal(drawing.type, SESSION_BOUNDARY_DRAWING_ID);
  assert.equal(drawing.paneIndex, 0);
  assert.equal(drawing.points.length, 6);
  assert.equal(drawing.colors.length, 6);
  assert.deepEqual(drawing.points[0], { timeIndex: 0, value: 100, paneIndex: 0 });
  assert.equal(drawing.colors[0], SESSION_ZONE_COLORS.asia);
  assert.ok(drawing.points.every((point) => Number.isFinite(point.timeIndex)));
});

test("renderer draws silent full-height dotted lines colored by session zone", () => {
  const drawing = {
    id: SESSION_BOUNDARY_DRAWING_ID,
    type: SESSION_BOUNDARY_DRAWING_ID,
    colors: [SESSION_ZONE_COLORS.asia, SESSION_ZONE_COLORS["new-york"]],
  };
  const pixelPoints = [
    [40, 300],
    [160, 300],
  ];
  const coordSys = { x: 0, y: 50, width: 800, height: 300 };

  const element = sessionBoundariesRenderer.render({ drawing, pixelPoints, coordSys });

  assert.equal(sessionBoundariesRenderer.type, SESSION_BOUNDARY_DRAWING_ID);
  assert.equal(element.type, "group");
  assert.equal(element.silent, true);
  assert.deepEqual(element.children, [
    {
      type: "line",
      shape: { x1: 40, y1: 50, x2: 40, y2: 350 },
      style: {
        stroke: SESSION_ZONE_COLORS.asia,
        lineWidth: SESSION_BOUNDARY_LINE_WIDTH,
        lineDash: SESSION_BOUNDARY_LINE_DASH,
      },
      silent: true,
    },
    {
      type: "line",
      shape: { x1: 160, y1: 50, x2: 160, y2: 350 },
      style: {
        stroke: SESSION_ZONE_COLORS["new-york"],
        lineWidth: SESSION_BOUNDARY_LINE_WIDTH,
        lineDash: SESSION_BOUNDARY_LINE_DASH,
      },
      silent: true,
    },
  ]);
});

test("renderer draws no text children and tolerates missing colors and points", () => {
  const drawing = { id: SESSION_BOUNDARY_DRAWING_ID, type: SESSION_BOUNDARY_DRAWING_ID };
  const element = sessionBoundariesRenderer.render({
    drawing,
    pixelPoints: [[10, 5], [null, 5], undefined],
    coordSys: { x: 0, y: 0, width: 400, height: 200 },
  });

  assert.equal(element.type, "group");
  assert.equal(element.silent, true);
  assert.equal(element.children.length, 1);
  assert.equal(element.children[0].type, "line");
  assert.equal(element.children[0].style.stroke, SESSION_BOUNDARY_LINE_COLOR);
  assert.ok(element.children.every((child) => child.type !== "text"));
});
