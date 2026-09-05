import assert from "node:assert/strict";
import { test } from "vitest";

import {
  BACKTEST_TRADE_DRAWING_ID,
  BACKTEST_TRADE_LINE_DASH,
  BACKTEST_TRADE_LINE_WIDTH,
  BACKTEST_TRADE_OPACITY,
  BACKTEST_ENTRY_TRIANGLE_SIZE,
  backtestTradesRenderer,
  buildBacktestTradesDrawing,
  tradeSegmentColor,
} from "./backtest-trade-plots.js";

function tradeRecord(time, trade) {
  return { time, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10, backtestTrade: trade };
}

test("colors win segments green, loss segments red, and everything else gray", () => {
  assert.equal(tradeSegmentColor("win"), "#22c55e");
  assert.equal(tradeSegmentColor("loss"), "#ef4444");
  assert.equal(tradeSegmentColor("breakeven"), "#a3a3a3");
  assert.equal(tradeSegmentColor("open"), "#a3a3a3");
  assert.equal(tradeSegmentColor(undefined), "#a3a3a3");
  assert.equal(tradeSegmentColor("unknown-outcome"), "#a3a3a3");
  assert.equal(tradeSegmentColor("WIN"), "#22c55e");
});

test("builds one batched drawing with entry-to-exit points for every trade", () => {
  const records = [
    tradeRecord(0, { id: 0, position: "buy", entry: 1.5, exit: 2.5, openTime: 0, closeTime: 2, result: "win" }),
    { time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    { time: 2, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    tradeRecord(3, { id: 1, position: "sell", entry: 2.5, exit: 1.8, openTime: 3, closeTime: 4, result: "breakeven" }),
    { time: 4, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    tradeRecord(5, { id: 2, entry: 1.5, openTime: 5, closeTime: 6, result: "win" }),
    { time: 6, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
  ];

  const drawing = buildBacktestTradesDrawing(records);

  assert.ok(drawing);
  assert.equal(drawing.id, BACKTEST_TRADE_DRAWING_ID);
  assert.equal(drawing.type, BACKTEST_TRADE_DRAWING_ID);
  assert.equal(drawing.paneIndex, 0);
  assert.deepEqual(drawing.style, { lineWidth: BACKTEST_TRADE_LINE_WIDTH });
  assert.deepEqual(drawing.points, [
    { timeIndex: 0, value: 1.5, paneIndex: 0 },
    { timeIndex: 2, value: 2.5, paneIndex: 0 },
    { timeIndex: 3, value: 2.5, paneIndex: 0 },
    { timeIndex: 4, value: 1.8, paneIndex: 0 },
  ]);
  assert.deepEqual(drawing.segmentColors, ["#22c55e", "#a3a3a3"]);
  assert.deepEqual(drawing.segmentPositions, ["buy", "sell"]);
});

test("returns null when no records carry renderable trades", () => {
  assert.equal(buildBacktestTradesDrawing([]), null);
  assert.equal(
    buildBacktestTradesDrawing([{ time: 0, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }]),
    null,
  );
  assert.equal(
    buildBacktestTradesDrawing([tradeRecord(0, { id: 0, entry: 1.5, openTime: 0, closeTime: 9, result: "win" })]),
    null,
  );
});

test("uses result trade-log entries when the CSV does not embed backtest columns", () => {
  const records = [
    { time: 1_700_000_000_000, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    { time: 1_700_000_900_000, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
  ];

  const drawing = buildBacktestTradesDrawing(records, [{
    position: "buy",
    entry: 1.5,
    exit: 1.8,
    open_time: "2023-11-14T22:13:20Z",
    close_time: "2023-11-14T22:28:20Z",
    result: "win",
  }]);

  assert.ok(drawing);
  assert.deepEqual(drawing.points, [
    { timeIndex: 0, value: 1.5, paneIndex: 0 },
    { timeIndex: 1, value: 1.8, paneIndex: 0 },
  ]);
  assert.deepEqual(drawing.segmentColors, ["#22c55e"]);
});

test("renderer draws dashed trade lines and directional entry triangles in drawing order", () => {
  const drawing = {
    id: BACKTEST_TRADE_DRAWING_ID,
    type: BACKTEST_TRADE_DRAWING_ID,
    segmentColors: ["#22c55e", "#ef4444"],
    segmentPositions: ["buy", "sell"],
    style: { lineWidth: 2 },
  };
  const pixelPoints = [
    [10, 40],
    [30, 20],
    [50, 60],
    [70, 80],
  ];

  const element = backtestTradesRenderer.render({ drawing, pixelPoints });

  assert.equal(backtestTradesRenderer.type, BACKTEST_TRADE_DRAWING_ID);
  assert.equal(element.type, "group");
  assert.equal(element.silent, true);
  assert.deepEqual(element.children, [
    {
      type: "line",
      shape: { x1: 10, y1: 40, x2: 30, y2: 20 },
      style: { stroke: "#22c55e", lineWidth: 2, lineDash: BACKTEST_TRADE_LINE_DASH, opacity: BACKTEST_TRADE_OPACITY },
      silent: true,
    },
    {
      type: "polygon",
      shape: { points: [[10, 40], [10 - BACKTEST_ENTRY_TRIANGLE_SIZE, 40 + BACKTEST_ENTRY_TRIANGLE_SIZE], [10 + BACKTEST_ENTRY_TRIANGLE_SIZE, 40 + BACKTEST_ENTRY_TRIANGLE_SIZE]] },
      style: { fill: "#22c55e", opacity: BACKTEST_TRADE_OPACITY },
      silent: true,
    },
    {
      type: "line",
      shape: { x1: 50, y1: 60, x2: 70, y2: 80 },
      style: { stroke: "#ef4444", lineWidth: 2, lineDash: BACKTEST_TRADE_LINE_DASH, opacity: BACKTEST_TRADE_OPACITY },
      silent: true,
    },
    {
      type: "polygon",
      shape: { points: [[50, 60], [50 - BACKTEST_ENTRY_TRIANGLE_SIZE, 60 - BACKTEST_ENTRY_TRIANGLE_SIZE], [50 + BACKTEST_ENTRY_TRIANGLE_SIZE, 60 - BACKTEST_ENTRY_TRIANGLE_SIZE]] },
      style: { fill: "#ef4444", opacity: BACKTEST_TRADE_OPACITY },
      silent: true,
    },
  ]);
});

test("renderer tolerates missing colors and incomplete point pairs", () => {
  const drawing = { id: BACKTEST_TRADE_DRAWING_ID, type: BACKTEST_TRADE_DRAWING_ID };

  const element = backtestTradesRenderer.render({ drawing, pixelPoints: [[5, 6]] });

  assert.deepEqual(element.children, []);

  const lone = backtestTradesRenderer.render({ drawing, pixelPoints: [[1, 2], [3, 4]] });
  assert.deepEqual(lone.children[0].style, {
    stroke: "#a3a3a3",
    lineWidth: BACKTEST_TRADE_LINE_WIDTH,
    lineDash: BACKTEST_TRADE_LINE_DASH,
    opacity: BACKTEST_TRADE_OPACITY,
  });
  assert.deepEqual(lone.children[1].shape.points, [[1, 2], [1 - BACKTEST_ENTRY_TRIANGLE_SIZE, 2 + BACKTEST_ENTRY_TRIANGLE_SIZE], [1 + BACKTEST_ENTRY_TRIANGLE_SIZE, 2 + BACKTEST_ENTRY_TRIANGLE_SIZE]]);
});
