const PRICE_ZONE_TYPES = new Set([
  "SUPPLY_ZONE",
  "DEMAND_ZONE",
  "SUPPORT_ZONE",
  "RESISTANCE_ZONE",
  "BULLISH_FVG",
  "BEARISH_FVG",
]);

const SESSION_LEVEL_TYPES = new Set([
  "LONDON_HIGH",
  "LONDON_LOW",
  "NEWYORK_HIGH",
  "NEWYORK_LOW",
  "ASIAN_HIGH",
  "ASIAN_LOW",
]);

export const VISIBLE_PRICE_RANGE_PADDING = 0.05;

export function priceZoneColumns(indicators) {
  if (!Array.isArray(indicators)) return [];
  return indicators
    .filter((indicator) => PRICE_ZONE_TYPES.has(indicator?.type))
    .flatMap((indicator) => Array.isArray(indicator.columns) ? indicator.columns : [])
    .filter((column) => typeof column === "string");
}

export function priceLevelColumns(indicators) {
  if (!Array.isArray(indicators)) return [];
  return indicators
    .filter((indicator) => PRICE_ZONE_TYPES.has(indicator?.type) || SESSION_LEVEL_TYPES.has(indicator?.type))
    .flatMap((indicator) => Array.isArray(indicator.columns) ? indicator.columns : [])
    .filter((column) => typeof column === "string");
}

export function visibleRecordIndexes(recordCount, categoryCount, zoomStart, zoomEnd) {
  if (!Number.isInteger(recordCount) || recordCount <= 0 || !Number.isInteger(categoryCount) || categoryCount < recordCount) return null;
  if (!Number.isFinite(zoomStart) || !Number.isFinite(zoomEnd)) return null;

  const padding = (categoryCount - recordCount) / 2;
  const firstCategory = Math.floor((Math.max(0, zoomStart) / 100) * categoryCount);
  const lastCategory = Math.ceil((Math.min(100, zoomEnd) / 100) * categoryCount) - 1;
  const start = Math.max(0, Math.floor(firstCategory - padding));
  const end = Math.min(recordCount - 1, Math.ceil(lastCategory - padding));
  return start <= end ? { start, end } : null;
}

export function visiblePriceRange(records, zoneColumns, viewport, padding = VISIBLE_PRICE_RANGE_PADDING) {
  const indexes = visibleRecordIndexes(
    records?.length ?? 0,
    viewport?.categoryCount,
    viewport?.start,
    viewport?.end,
  );
  if (!indexes) return null;

  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (let index = indexes.start; index <= indexes.end; index += 1) {
    const record = records[index];
    for (const value of [record?.low, record?.high, ...(zoneColumns.map((column) => record?.[column]))]) {
      if (!Number.isFinite(value)) continue;
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return null;

  const range = max - min;
  const fallbackRange = Math.max(Math.abs(max) * 0.01, 1e-8);
  const buffer = (range || fallbackRange) * padding;
  return { min: min - buffer, max: max + buffer, indexes };
}
