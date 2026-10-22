import { marketTimeframeBucket } from "../../../shared/lib/market-data.js";

export const PREV_WEEK_ZONES_DRAWING_ID = "prev-week-zones";
export const PREV_WEEK_ZONES_COLOR = "#7f7f7f";
export const PREV_WEEK_ZONE_LINE_WIDTH = 0.8;
export const PREV_WEEK_LEVEL_LINE_WIDTH = 1.5;
export const PREV_WEEK_LEVEL_LINE_DASH = [4, 4];
export const PREV_WEEK_ZONE_LABEL_FONT = "10px sans-serif";
export const PREV_WEEK_LEVEL_LABEL_FONT = "12px sans-serif";
export const PREV_WEEK_LABEL_BACKGROUND = "rgba(255, 255, 255, 0.75)";

const ZONE_COLORS = {
  resistance: { stroke: "#d62728", fill: "rgba(214, 39, 40, 0.18)" },
  support: { stroke: "#2ca02c", fill: "rgba(44, 160, 44, 0.18)" },
  neutral: { stroke: "#7f7f7f", fill: "rgba(127, 127, 127, 0.18)" },
};

function zoneColor(type) {
  return ZONE_COLORS[type] ?? ZONE_COLORS.neutral;
}

function zoneType(record, column) {
  const value = record?.[column];
  return typeof value === "string" && ZONE_COLORS[value] ? value : "neutral";
}

function prevWeekZoneColumns(indicators) {
  const entry = Array.isArray(indicators)
    ? indicators.find((indicator) => indicator?.type === "PREV_WEEK_ZONES")
    : null;
  if (!entry || !Array.isArray(entry.columns)) return null;

  const column = (stem) => entry.columns.find((name) => name === stem || name.startsWith(`${stem}_`));

  const slots = [];
  for (let slot = 1; slot <= 5; slot += 1) {
    const low = column(`prev_week_zone${slot}_low`);
    const high = column(`prev_week_zone${slot}_high`);
    if (!low || !high) continue;
    slots.push({
      low,
      high,
      type: column(`prev_week_zone${slot}_type`),
      source: column(`prev_week_zone${slot}_source`),
    });
  }

  return {
    slots,
    highLevel: column("prev_week_high_level"),
    lowLevel: column("prev_week_low_level"),
    atr: column("prev_week_atr"),
  };
}

function weeklyZoneSegments(records, slot) {
  const segments = [];
  let current;

  records.forEach((record, index) => {
    const low = record[slot.low];
    const high = record[slot.high];
    if (!Number.isFinite(low) || !Number.isFinite(high)) {
      current = null;
      return;
    }
    const type = zoneType(record, slot.type);
    const source = String(record[slot.source] ?? "");

    if (current && current.low === low && current.high === high && current.type === type && current.source === source) {
      current.endIndex = index;
      return;
    }

    current = { low, high, type, source, startIndex: index, endIndex: index };
    segments.push(current);
  });

  return segments;
}

function weeklyLevelSegments(records, column) {
  if (!column) return [];
  const segments = [];
  let current;

  records.forEach((record, index) => {
    const value = record[column];
    if (!Number.isFinite(value)) {
      current = null;
      return;
    }
    if (current && current.value === value) {
      current.endIndex = index;
      return;
    }
    current = { value, startIndex: index, endIndex: index };
    segments.push(current);
  });

  return segments;
}

function zoneLevel(segment) {
  return (segment.low + segment.high) / 2;
}

function sourceLabel(source) {
  const parts = String(source ?? "").split("+").filter(Boolean);
  if (parts.length > 2) return `${parts[0]}+${parts.length - 1}`;
  return parts.join("+");
}

function weekKey(records, segment) {
  return marketTimeframeBucket(records[segment.startIndex].time, "W1");
}

function zoneLabels(records, segments, columns) {
  const byWeek = new Map();
  for (const segment of segments) {
    const key = weekKey(records, segment);
    if (key === null) continue;
    if (!byWeek.has(key)) byWeek.set(key, []);
    byWeek.get(key).push(segment);
  }

  const labels = [];

  for (const weekSegments of byWeek.values()) {
    const ordered = [...weekSegments].sort((left, right) => zoneLevel(left) - zoneLevel(right));
    const supportRank = new Map();
    const supports = ordered.filter((segment) => segment.type === "support");
    supports.forEach((segment, index) => supportRank.set(segment, supports.length - index));

    const counters = { resistance: 0, neutral: 0 };
    let lastLabelLevel;

    for (const segment of ordered) {
      const level = zoneLevel(segment);
      const atr = columns.atr ? records[segment.startIndex]?.[columns.atr] : undefined;

      if (
        Number.isFinite(atr)
        && atr > 0
        && lastLabelLevel !== undefined
        && Math.abs(level - lastLabelLevel) < 0.75 * atr
      ) {
        continue;
      }

      let label;
      if (segment.type === "support") {
        label = `S${supportRank.get(segment)}`;
      } else if (segment.type === "resistance") {
        counters.resistance += 1;
        label = `R${counters.resistance}`;
      } else {
        counters.neutral += 1;
        label = `N${counters.neutral}`;
      }

      lastLabelLevel = level;
      labels.push({
        segment,
        text: `${label} ${sourceLabel(segment.source)} `,
        color: zoneColor(segment.type).stroke,
      });
    }
  }

  return labels;
}

/**
 * Build one batched QFChart drawing replicating the bos_liquidity_sweep
 * previous-week zone plot: merged zones drawn across the current week,
 * PWH/PWL dashed levels and R/S/N labels.
 */
export function buildPrevWeekZonesDrawing(records, indicators) {
  const columns = prevWeekZoneColumns(indicators);
  if (!columns || columns.slots.length === 0 || !Array.isArray(records) || records.length === 0) {
    return null;
  }

  const points = [];
  const rectStyles = [];
  const lineStyles = [];
  const labels = [];

  const zoneSegments = [];

  for (const slot of columns.slots) {
    for (const segment of weeklyZoneSegments(records, slot)) {
      points.push(
        { timeIndex: segment.startIndex - 0.5, value: segment.high, paneIndex: 0 },
        { timeIndex: segment.endIndex + 0.5, value: segment.low, paneIndex: 0 },
      );
      const color = zoneColor(segment.type);
      rectStyles.push({ fill: color.fill, stroke: color.stroke });
      zoneSegments.push(segment);
    }
  }

  const levelLabels = [];

  for (const [column, text, verticalAlign] of [
    [columns.highLevel, " PWH", "bottom"],
    [columns.lowLevel, " PWL", "top"],
  ]) {
    for (const segment of weeklyLevelSegments(records, column)) {
      points.push(
        { timeIndex: segment.startIndex - 0.5, value: segment.value, paneIndex: 0 },
        { timeIndex: segment.endIndex + 0.5, value: segment.value, paneIndex: 0 },
      );
      lineStyles.push({ color: PREV_WEEK_ZONES_COLOR });
      levelLabels.push({ segment, text, verticalAlign });
    }
  }

  if (points.length === 0) return null;

  for (const { segment, text, verticalAlign } of levelLabels) {
    points.push({ timeIndex: segment.startIndex, value: segment.value, paneIndex: 0 });
    labels.push({
      text,
      color: PREV_WEEK_ZONES_COLOR,
      align: "left",
      verticalAlign,
      font: PREV_WEEK_LEVEL_LABEL_FONT,
    });
  }

  for (const label of zoneLabels(records, zoneSegments, columns)) {
    points.push({ timeIndex: label.segment.endIndex, value: zoneLevel(label.segment), paneIndex: 0 });
    labels.push({
      text: label.text,
      color: label.color,
      align: "right",
      verticalAlign: "middle",
      font: PREV_WEEK_ZONE_LABEL_FONT,
    });
  }

  return {
    id: PREV_WEEK_ZONES_DRAWING_ID,
    type: PREV_WEEK_ZONES_DRAWING_ID,
    paneIndex: 0,
    points,
    rectStyles,
    lineStyles,
    labels,
  };
}

/** Render zone rectangles, dashed levels and text labels from the drawing. */
export const prevWeekZonesRenderer = {
  type: PREV_WEEK_ZONES_DRAWING_ID,
  render({ drawing, pixelPoints }) {
    const rectStyles = Array.isArray(drawing.rectStyles) ? drawing.rectStyles : [];
    const lineStyles = Array.isArray(drawing.lineStyles) ? drawing.lineStyles : [];
    const labels = Array.isArray(drawing.labels) ? drawing.labels : [];
    const points = Array.isArray(pixelPoints) ? pixelPoints : [];
    const children = [];
    let cursor = 0;

    for (const style of rectStyles) {
      const [x1, y1] = points[cursor] ?? [];
      const [x2, y2] = points[cursor + 1] ?? [];
      cursor += 2;
      if (![x1, y1, x2, y2].every(Number.isFinite)) continue;
      children.push({
        type: "rect",
        shape: {
          x: Math.min(x1, x2),
          y: Math.min(y1, y2),
          width: Math.abs(x2 - x1),
          height: Math.abs(y2 - y1),
        },
        style: {
          fill: style.fill,
          stroke: style.stroke,
          lineWidth: PREV_WEEK_ZONE_LINE_WIDTH,
        },
        silent: true,
      });
    }

    for (const style of lineStyles) {
      const [x1, y1] = points[cursor] ?? [];
      const [x2, y2] = points[cursor + 1] ?? [];
      cursor += 2;
      if (![x1, y1, x2, y2].every(Number.isFinite)) continue;
      children.push({
        type: "line",
        shape: { x1, y1, x2, y2 },
        style: {
          stroke: style.color,
          lineWidth: PREV_WEEK_LEVEL_LINE_WIDTH,
          lineDash: PREV_WEEK_LEVEL_LINE_DASH,
        },
        silent: true,
      });
    }

    for (const label of labels) {
      const [x, y] = points[cursor] ?? [];
      cursor += 1;
      if (![x, y].every(Number.isFinite)) continue;
      children.push({
        type: "text",
        style: {
          text: label.text,
          x,
          y,
          fill: label.color,
          font: label.font ?? PREV_WEEK_ZONE_LABEL_FONT,
          align: label.align ?? "right",
          verticalAlign: label.verticalAlign ?? "middle",
          backgroundColor: PREV_WEEK_LABEL_BACKGROUND,
          padding: [2, 3],
        },
        silent: true,
      });
    }

    return { type: "group", children, silent: true };
  },
};
