/**
 * UTC session-boundary markers: persistent, non-interactive, full-height
 * dotted vertical lines drawn on the market chart at the start and end of
 * every UTC trading session that falls inside the loaded candles.
 *
 * Each line uses the same color family as its session-zone indicator (amber
 * for Asia, blue for London, purple for New York). The London–New York
 * overlap starts and ends exactly when New York starts and London ends, so
 * those boundaries are covered by the New York start and London end lines.
 *
 * Boundaries are anchored to a candle's own index when they coincide with a
 * candle open time, and to the exact fractional candle index when they fall
 * inside a larger timeframe candle span. Boundaries outside the loaded data
 * range are omitted.
 */

export const SESSION_BOUNDARY_DRAWING_ID = "session-boundaries";
export const SESSION_BOUNDARY_LINE_WIDTH = 1;
export const SESSION_BOUNDARY_LINE_DASH = [1, 3];
export const SESSION_BOUNDARY_LINE_COLOR = "#52525b";

export const SESSION_ZONE_COLORS = {
  asia: "#FFB300",
  london: "#42A5F5",
  "new-york": "#AB47BC",
};

const SESSION_SCHEDULES = [
  { name: "Asia", key: "asia", startHour: 0, endHour: 9 },
  { name: "London", key: "london", startHour: 8, endHour: 17 },
  { name: "New York", key: "new-york", startHour: 13, endHour: 22 },
];

/**
 * UTC session start/end hours with the session-zone color of the session that
 * boundary belongs to, in chronological order.
 */
export function sessionBoundaryHours() {
  const colorsByHour = new Map();
  for (const schedule of SESSION_SCHEDULES) {
    for (const hour of [schedule.startHour, schedule.endHour]) {
      if (!colorsByHour.has(hour)) colorsByHour.set(hour, SESSION_ZONE_COLORS[schedule.key]);
    }
  }
  return [...colorsByHour.entries()].sort(([left], [right]) => left - right);
}

function recordTime(record) {
  const time = Number(record?.time);
  return Number.isFinite(time) ? time : null;
}

function anchorPrice(record) {
  for (const field of ["open", "high", "low", "close"]) {
    const value = Number(record?.[field]);
    if (Number.isFinite(value)) return value;
  }
  return 0;
}

/**
 * Position one boundary instant between the surrounding candles. Records must
 * be sorted ascending by time. Returns the anchor record's price as the value
 * and either the exact candle index (aligned boundary) or a fractional index
 * (intra-candle boundary). Returns null when the instant cannot be placed.
 */
function boundaryMarkerAt(records, timedIndexes, time, color) {
  let low = 0;
  let high = timedIndexes.length - 1;
  let at = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    const recordIndex = timedIndexes[mid];
    if (records[recordIndex].time <= time) {
      at = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  if (at < 0) return null;

  const recordIndex = timedIndexes[at];
  const record = records[recordIndex];
  if (record.time === time) {
    return { time, timeIndex: recordIndex, value: anchorPrice(record), color };
  }

  const nextRecord = at + 1 < timedIndexes.length ? records[timedIndexes[at + 1]] : null;
  if (!nextRecord) return null;
  const span = nextRecord.time - record.time;
  if (!Number.isFinite(span) || span <= 0) return null;
  return {
    time,
    timeIndex: recordIndex + (time - record.time) / span,
    value: anchorPrice(record),
    color,
  };
}

/**
 * Build the UTC session-boundary markers for the loaded candles. Every UTC day
 * present in the records contributes markers at 00:00, 08:00, 09:00, 13:00,
 * 17:00, and 22:00, but only when the boundary instant falls inside the loaded
 * data range. Each marker carries the session-zone color of its boundary.
 */
export function sessionBoundaryMarkers(records) {
  if (!Array.isArray(records) || records.length === 0) return [];

  let minTime = Number.POSITIVE_INFINITY;
  let maxTime = Number.NEGATIVE_INFINITY;
  const days = new Set();
  const timedIndexes = [];
  for (let index = 0; index < records.length; index += 1) {
    const time = recordTime(records[index]);
    if (time === null) continue;
    timedIndexes.push(index);
    if (time < minTime) minTime = time;
    if (time > maxTime) maxTime = time;
    days.add(new Date(time).toISOString().slice(0, 10));
  }
  if (timedIndexes.length === 0) return [];

  const hourColors = sessionBoundaryHours();
  const markers = [];
  for (const day of [...days].sort()) {
    for (const [hour, color] of hourColors) {
      const time = Date.parse(`${day}T${String(hour).padStart(2, "0")}:00:00Z`);
      if (time < minTime || time > maxTime) continue;
      const marker = boundaryMarkerAt(records, timedIndexes, time, color);
      if (marker) markers.push(marker);
    }
  }
  return markers.sort((left, right) => left.time - right.time);
}

/**
 * Build one batched QFChart drawing holding every session-boundary marker.
 * Returns null when no boundary falls inside the loaded candles so the chart
 * stays untouched.
 */
export function buildSessionBoundariesDrawing(records) {
  const markers = sessionBoundaryMarkers(records);
  if (markers.length === 0) return null;
  return {
    id: SESSION_BOUNDARY_DRAWING_ID,
    type: SESSION_BOUNDARY_DRAWING_ID,
    points: markers.map((marker) => ({ timeIndex: marker.timeIndex, value: marker.value, paneIndex: 0 })),
    colors: markers.map((marker) => marker.color),
    paneIndex: 0,
  };
}

/**
 * Non-interactive QFChart drawing renderer: one silent full-height dotted
 * vertical line per marker, colored by the session the boundary belongs to.
 */
export const sessionBoundariesRenderer = {
  type: SESSION_BOUNDARY_DRAWING_ID,
  render({ drawing, pixelPoints, coordSys }) {
    const colors = Array.isArray(drawing?.colors) ? drawing.colors : [];
    const points = Array.isArray(pixelPoints) ? pixelPoints : [];
    const top = coordSys && Number.isFinite(coordSys.y) ? coordSys.y : 0;
    const bottom = coordSys && Number.isFinite(coordSys.height) ? top + coordSys.height : top;

    const children = [];
    points.forEach((point, index) => {
      const x = point && Number.isFinite(point[0]) ? point[0] : null;
      if (x === null) return;
      const color = typeof colors[index] === "string" ? colors[index] : SESSION_BOUNDARY_LINE_COLOR;
      children.push({
        type: "line",
        shape: { x1: x, y1: top, x2: x, y2: bottom },
        style: {
          stroke: color,
          lineWidth: SESSION_BOUNDARY_LINE_WIDTH,
          lineDash: SESSION_BOUNDARY_LINE_DASH,
        },
        silent: true,
      });
    });
    return { type: "group", children, silent: true };
  },
};
