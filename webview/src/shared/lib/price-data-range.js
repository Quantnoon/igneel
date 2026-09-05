import { parseCsv, toEpochMilliseconds } from "./market-data.js";

const DAY_MS = 24 * 60 * 60 * 1000;

function utcDay(timestamp) {
  const date = new Date(timestamp);
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
}

export function extractPriceDataRange(csvText) {
  const rows = parseCsv(csvText);
  if (!rows.length) return null;

  const headers = rows[0].map((header, index) => index === 0 ? header.replace(/^\uFEFF/, "") : header);
  const timeIndex = headers.indexOf("time");
  if (timeIndex < 0) return null;

  let start = Number.POSITIVE_INFINITY;
  let end = Number.NEGATIVE_INFINITY;
  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    try {
      const timestamp = toEpochMilliseconds(rows[rowIndex][timeIndex] ?? "", rowIndex + 1);
      start = Math.min(start, timestamp);
      end = Math.max(end, timestamp);
    } catch {
      // A malformed price row should not hide an otherwise valid data range.
    }
  }

  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  return {
    start,
    end,
    elapsedDays: Math.round((utcDay(end) - utcDay(start)) / DAY_MS),
  };
}

export function formatUtcDate(timestamp) {
  if (!Number.isFinite(timestamp)) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(timestamp);
}
