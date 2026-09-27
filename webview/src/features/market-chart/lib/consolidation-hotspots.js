export const CONSOLIDATION_HOTSPOT_DRAWING_ID = "consolidation-hotspots";
export const CONSOLIDATION_HOTSPOT_COLOR = "#F97316";
export const CONSOLIDATION_HOTSPOT_FILL = "rgba(249, 115, 22, 0.18)";
export const CONSOLIDATION_HOTSPOT_LINE_WIDTH = 1;

function consolidationColumns(indicators) {
  const entry = Array.isArray(indicators)
    ? indicators.find((indicator) => indicator?.type === "CONSOLIDATION_HOTSPOT")
    : null;
  if (!entry || !Array.isArray(entry.columns)) return null;

  const column = (stem) => entry.columns.find((name) => {
    if (stem === "consolidation") return /^consolidation_[A-Za-z0-9]+$/i.test(name);
    return name.startsWith(`${stem}_`);
  });
  const result = {
    active: column("consolidation"),
    id: column("consolidation_id"),
    high: column("consolidation_high"),
    low: column("consolidation_low"),
  };
  return Object.values(result).every(Boolean) ? result : null;
}

/** Build contiguous, valid consolidation ranges from the configured CSV fields. */
export function consolidationHotspots(records, indicators) {
  const columns = consolidationColumns(indicators);
  if (!columns || !Array.isArray(records)) return [];

  const hotspots = [];
  let active;
  const finish = () => {
    if (active) hotspots.push(active);
    active = null;
  };

  records.forEach((record, index) => {
    const id = record?.[columns.id];
    const high = record?.[columns.high];
    const low = record?.[columns.low];
    const valid = record?.[columns.active] === true
      && id !== undefined
      && id !== null
      && Number.isFinite(high)
      && Number.isFinite(low)
      && high >= low;

    if (!valid) {
      finish();
      return;
    }

    if (active && (active.id !== id || active.high !== high || active.low !== low)) finish();
    if (!active) active = { id, high, low, startIndex: index, endIndex: index };
    else active.endIndex = index;
  });
  finish();
  return hotspots;
}

/** Build a single batched drawing with two points per hotspot rectangle. */
export function buildConsolidationHotspotsDrawing(records, indicators) {
  const hotspots = consolidationHotspots(records, indicators);
  if (hotspots.length === 0) return null;
  return {
    id: CONSOLIDATION_HOTSPOT_DRAWING_ID,
    type: CONSOLIDATION_HOTSPOT_DRAWING_ID,
    paneIndex: 0,
    points: hotspots.flatMap((hotspot) => [
      { timeIndex: hotspot.startIndex - 0.5, value: hotspot.high, paneIndex: 0 },
      { timeIndex: hotspot.endIndex + 0.5, value: hotspot.low, paneIndex: 0 },
    ]),
  };
}

/** Render each point pair as a silent translucent range band. */
export const consolidationHotspotsRenderer = {
  type: CONSOLIDATION_HOTSPOT_DRAWING_ID,
  render({ pixelPoints }) {
    const points = Array.isArray(pixelPoints) ? pixelPoints : [];
    const children = [];
    for (let index = 0; index + 1 < points.length; index += 2) {
      const [x1, y1] = points[index] ?? [];
      const [x2, y2] = points[index + 1] ?? [];
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
          fill: CONSOLIDATION_HOTSPOT_FILL,
          stroke: CONSOLIDATION_HOTSPOT_COLOR,
          lineWidth: CONSOLIDATION_HOTSPOT_LINE_WIDTH,
        },
        silent: true,
      });
    }
    return { type: "group", children, silent: true };
  },
};
