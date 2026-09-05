const CANDLE_FIELDS = ["open", "high", "low", "close", "volume"];

const TIMEFRAME_ORDER = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"];

function timeframeRank(timeframe) {
  return TIMEFRAME_ORDER.indexOf(String(timeframe ?? "").toUpperCase());
}

function columnTimeframe(column) {
  const match = String(column).match(/_([^_]+)$/);
  if (!match || timeframeRank(match[1]) === -1) return null;
  return match[1].toUpperCase();
}

export function rawIndicatorPoints(records, column) {
  return records
    .filter((record) => Number.isFinite(record[column]))
    .map((record) => ({ time: record.time, value: record[column] }));
}

export function interpolateIndicatorPoints(records, column, entryTf) {
  const recordIndexes = new Map(records.map((record, index) => [record.time, index]));
  const raw = rawIndicatorPoints(records, column).map((point) => ({
    ...point,
    index: recordIndexes.get(point.time),
  }));

  const entryRank = timeframeRank(entryTf);
  const columnRank = timeframeRank(columnTimeframe(column));
  if (entryRank === -1 || columnRank <= entryRank || raw.length < 2) {
    return raw.map(({ time, value }) => ({ time, value }));
  }

  const anchors = [];
  let previous;
  for (const point of raw) {
    if (previous === undefined || point.value !== previous) anchors.push(point);
    previous = point.value;
  }
  if (anchors.length < 2) {
    return raw.map(({ time, value }) => ({ time, value }));
  }

  const values = new Map(raw.map((point) => [point.index, point.value]));
  for (let anchorIndex = 0; anchorIndex < anchors.length - 1; anchorIndex += 1) {
    const from = anchors[anchorIndex];
    const to = anchors[anchorIndex + 1];
    for (let index = from.index + 1; index < to.index; index += 1) {
      const ratio = (index - from.index) / (to.index - from.index);
      values.set(index, from.value + (to.value - from.value) * ratio);
    }
  }

  return records
    .map((record, index) => ({ time: record.time, value: values.get(index) }))
    .filter((point) => point.value !== undefined);
}

export function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        field += character;
      }
    } else if (character === '"') {
      quoted = true;
    } else if (character === ",") {
      row.push(field);
      field = "";
    } else if (character === "\n") {
      row.push(field.endsWith("\r") ? field.slice(0, -1) : field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += character;
    }
  }

  if (quoted) throw new Error("CSV contains an unterminated quoted field.");
  if (field !== "" || row.length > 0) {
    row.push(field.endsWith("\r") ? field.slice(0, -1) : field);
    rows.push(row);
  }
  return rows;
}

export function toEpochMilliseconds(value, rowNumber) {
  const timestamp = value.trim();
  if (!timestamp) throw new Error(`Row ${rowNumber}: time is missing.`);

  const normalized = timestamp.includes("T") ? timestamp : timestamp.replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized);
  const milliseconds = Date.parse(hasTimezone ? normalized : `${normalized}Z`);
  if (!Number.isFinite(milliseconds)) {
    throw new Error(`Row ${rowNumber}: invalid time value ${JSON.stringify(value)}.`);
  }
  return milliseconds;
}

export function collapseEntryCandles(records) {
  const collapsed = [];
  for (const record of records) {
    const last = collapsed[collapsed.length - 1];
    if (
      last !== undefined &&
      last.open === record.open &&
      last.high === record.high &&
      last.low === record.low &&
      last.close === record.close &&
      last.volume === record.volume
    ) {
      continue;
    }
    collapsed.push(record);
  }
  return collapsed;
}

export function convertMarketData(csvText, entryTf, indicatorColumns = []) {
  if (typeof entryTf !== "string" || !entryTf.trim()) {
    throw new Error("config.json must contain a non-empty entry_tf value.");
  }

  const rows = parseCsv(csvText);
  if (rows.length === 0) throw new Error("CSV is empty.");
  const headers = rows[0].map((header, index) => index === 0 ? header.replace(/^\uFEFF/, "") : header);
  const required = ["time", ...CANDLE_FIELDS.map((field) => `${field}_${entryTf}`)];
  const indexes = Object.fromEntries(required.map((column) => [column, headers.indexOf(column)]));
  const missing = required.filter((column) => indexes[column] < 0);
  if (missing.length > 0) {
    throw new Error(`Missing required columns for ${entryTf}: ${missing.join(", ")}.`);
  }

  const requestedColumns = Array.isArray(indicatorColumns) ? indicatorColumns : [];
  const indicatorIndexes = requestedColumns
    .map((column) => ({ column, index: headers.indexOf(column) }))
    .filter((entry) => entry.index >= 0);

  const records = [];
  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex];
    if (row.length === 1 && row[0] === "") continue;
    const values = CANDLE_FIELDS.map((field) => row[indexes[`${field}_${entryTf}`]] ?? "");
    if (values.some((value) => value.trim() === "")) continue;

    const candle = { time: toEpochMilliseconds(row[indexes.time] ?? "", rowIndex + 1) };
    CANDLE_FIELDS.forEach((field, fieldIndex) => {
      const rawValue = values[fieldIndex];
      const number = Number(rawValue);
      if (!Number.isFinite(number)) {
        throw new Error(`Row ${rowIndex + 1}: ${field}_${entryTf} is not a finite number: ${JSON.stringify(rawValue)}.`);
      }
      candle[field] = number;
    });
    for (const { column, index } of indicatorIndexes) {
      const rawValue = row[index] ?? "";
      if (rawValue.trim() === "") continue;
      const number = Number(rawValue);
      if (Number.isFinite(number)) candle[column] = number;
    }
    records.push(candle);
  }

  if (records.length === 0) {
    throw new Error(`No usable candle rows were found for ${entryTf}.`);
  }
  return collapseEntryCandles(records);
}
