import { backtestTradeSegments } from "../../../shared/lib/market-data.js";

export const BACKTEST_TRADE_DRAWING_ID = "backtest-trades";
export const BACKTEST_TRADE_LINE_WIDTH = 1.5;
export const BACKTEST_TRADE_LINE_DASH = [4, 4];
export const BACKTEST_TRADE_OPACITY = 0.6;
export const BACKTEST_ENTRY_TRIANGLE_SIZE = 6;

const TRADE_SEGMENT_COLORS = {
  win: "#22c55e",
  loss: "#ef4444",
};
const DEFAULT_TRADE_SEGMENT_COLOR = "#a3a3a3";

export function tradeSegmentColor(result) {
  const color = TRADE_SEGMENT_COLORS[String(result ?? "").toLowerCase()];
  return color ?? DEFAULT_TRADE_SEGMENT_COLOR;
}

/**
 * Build one batched QFChart drawing holding every trade segment, drawn from
 * (open_time, entry) to (close_time, exit). Returns null when there are no
 * renderable trades so the chart stays untouched.
 */
function nearestCandleIndex(records, timestamp) {
  if (!Number.isFinite(timestamp) || records.length === 0) return undefined;

  let nearestIndex = 0;
  let nearestDistance = Math.abs(records[0].time - timestamp);
  for (let index = 1; index < records.length; index += 1) {
    const distance = Math.abs(records[index].time - timestamp);
    if (distance < nearestDistance) {
      nearestIndex = index;
      nearestDistance = distance;
    }
  }
  return nearestIndex;
}

function resultTradeSegments(records, trades) {
  if (!Array.isArray(trades)) return [];
  return trades.flatMap((trade, index) => {
    const entryPrice = Number(trade?.entry);
    const exitPrice = Number(trade?.exit);
    const openTime = Date.parse(trade?.open_time);
    const closeTime = Date.parse(trade?.close_time);
    const startIndex = nearestCandleIndex(records, openTime);
    const endIndex = nearestCandleIndex(records, closeTime);
    if (!Number.isFinite(entryPrice) || !Number.isFinite(exitPrice) || startIndex === undefined || endIndex === undefined) return [];
    return [{
      id: trade.id ?? index,
      position: trade.position,
      result: trade.result,
      entryPrice,
      exitPrice,
      startIndex,
      endIndex,
    }];
  });
}

export function buildBacktestTradesDrawing(records, resultTrades = []) {
  const embeddedSegments = backtestTradeSegments(records);
  const segments = embeddedSegments.length > 0 ? embeddedSegments : resultTradeSegments(records, resultTrades);
  if (segments.length === 0) return null;

  const points = [];
  const segmentColors = [];
  const segmentPositions = [];
  for (const segment of segments) {
    points.push(
      { timeIndex: segment.startIndex, value: segment.entryPrice, paneIndex: 0 },
      { timeIndex: segment.endIndex, value: segment.exitPrice, paneIndex: 0 },
    );
    segmentColors.push(tradeSegmentColor(segment.result));
    segmentPositions.push(String(segment.position ?? "").toLowerCase());
  }

  return {
    id: BACKTEST_TRADE_DRAWING_ID,
    type: BACKTEST_TRADE_DRAWING_ID,
    points,
    paneIndex: 0,
    segmentColors,
    segmentPositions,
    style: { lineWidth: BACKTEST_TRADE_LINE_WIDTH },
  };
}

/**
 * Non-interactive QFChart drawing renderer: one silent line child per trade
 * segment, colored by outcome. Consecutive point pairs form the segments.
 */
export const backtestTradesRenderer = {
  type: BACKTEST_TRADE_DRAWING_ID,
  render({ drawing, pixelPoints }) {
    const segmentColors = Array.isArray(drawing.segmentColors) ? drawing.segmentColors : [];
    const segmentPositions = Array.isArray(drawing.segmentPositions) ? drawing.segmentPositions : [];
    const lineWidth = drawing.style?.lineWidth ?? BACKTEST_TRADE_LINE_WIDTH;
    const children = [];
    for (let index = 0; index + 1 < pixelPoints.length; index += 2) {
      const [x1, y1] = pixelPoints[index];
      const [x2, y2] = pixelPoints[index + 1];
      const color = segmentColors[index / 2] ?? DEFAULT_TRADE_SEGMENT_COLOR;
      const triangleSize = BACKTEST_ENTRY_TRIANGLE_SIZE;
      const isSell = segmentPositions[index / 2] === "sell";
      children.push({
        type: "line",
        shape: { x1, y1, x2, y2 },
        style: {
          stroke: color,
          lineWidth,
          lineDash: BACKTEST_TRADE_LINE_DASH,
          opacity: BACKTEST_TRADE_OPACITY,
        },
        silent: true,
      });
      children.push({
        type: "polygon",
        shape: {
          points: isSell
            ? [[x1, y1], [x1 - triangleSize, y1 - triangleSize], [x1 + triangleSize, y1 - triangleSize]]
            : [[x1, y1], [x1 - triangleSize, y1 + triangleSize], [x1 + triangleSize, y1 + triangleSize]],
        },
        style: { fill: color, opacity: BACKTEST_TRADE_OPACITY },
        silent: true,
      });
    }
    return { type: "group", children, silent: true };
  },
};
