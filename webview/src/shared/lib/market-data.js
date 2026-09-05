/** Pure CSV and market-series transformations shared by the chart feature. */
const CANDLE_FIELDS = ["open", "high", "low", "close", "volume"];

const TIMEFRAME_ORDER = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"];

const BACKTEST_TRADE_PREFIX = "backtest_";
const BACKTEST_TRADE_ID_COLUMN = `${BACKTEST_TRADE_PREFIX}trade_id`;
const BACKTEST_TRADE_FIELD_KINDS = {
  number: [
    ["trade_id", "id"],
    ["entry", "entry"],
    ["exit", "exit"],
    ["sl", "sl"],
    ["tp", "tp"],
    ["pnl", "pnl"],
    ["pnl_dollar", "pnlDollar"],
    ["pnl_currency", "pnlCurrency"],
    ["balance_before", "balanceBefore"],
    ["balance_after", "balanceAfter"],
  ],
  text: [
    ["position", "position"],
    ["result", "result"],
    ["session", "session"],
    ["day", "day"],
    ["skip_reason", "skipReason"],
  ],
  time: [
    ["open_time", "openTime"],
    ["close_time", "closeTime"],
  ],
  boolean: [
    ["skipped", "skipped"],
  ],
};

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

export function stepIndicatorPoints(records, column) {
  let value;
  let hasValue = false;
  return records.flatMap((record) => {
    if (Number.isFinite(record[column])) {
      value = record[column];
      hasValue = true;
    }
    return hasValue ? [{ time: record.time, value }] : [];
  });
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

export function collapseEntryCandles(records, preserveTimes) {
  const keep = preserveTimes instanceof Set ? preserveTimes : null;
  const collapsed = [];
  for (const record of records) {
    const last = collapsed[collapsed.length - 1];
    const preserved = keep !== null && keep.has(record.time);
    if (
      !preserved &&
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

function parseBacktestTrade(row, fieldIndexes) {
  const trade = {};
  for (const { index, key, kind } of fieldIndexes) {
    const raw = row[index] ?? "";
    if (raw.trim() === "") continue;
    if (kind === "number") {
      const number = Number(raw);
      if (Number.isFinite(number)) trade[key] = number;
    } else if (kind === "time") {
      try {
        trade[key] = toEpochMilliseconds(raw, 0);
      } catch {
        // Ignore malformed trade timestamps; the trade is dropped later.
      }
    } else if (kind === "boolean") {
      const lowered = raw.trim().toLowerCase();
      if (lowered === "true") trade[key] = true;
      else if (lowered === "false") trade[key] = false;
    } else {
      trade[key] = raw.trim();
    }
  }
  return trade;
}

function backtestTradeFieldIndexes(headers) {
  if (headers.indexOf(BACKTEST_TRADE_ID_COLUMN) < 0) return [];
  const indexes = [];
  for (const [kind, fields] of Object.entries(BACKTEST_TRADE_FIELD_KINDS)) {
    for (const [column, key] of fields) {
      const index = headers.indexOf(`${BACKTEST_TRADE_PREFIX}${column}`);
      if (index >= 0) indexes.push({ index, key, kind });
    }
  }
  return indexes;
}

/**
 * Build entry-to-exit segments from records carrying backtest trades.
 * Each segment anchors its endpoints to candle indexes so the chart can
 * draw a straight line from (open_time, entry) to (close_time, exit).
 * Incomplete or malformed trades are ignored.
 */
export function backtestTradeSegments(records) {
  const indexByTime = new Map(records.map((record, index) => [record.time, index]));
  const segments = [];
  for (const record of records) {
    const trade = record.backtestTrade;
    if (!trade) continue;
    if (!Number.isFinite(trade.entry) || !Number.isFinite(trade.exit)) continue;
    const startIndex = indexByTime.get(trade.openTime);
    const endIndex = indexByTime.get(trade.closeTime);
    if (startIndex === undefined || endIndex === undefined) continue;
    segments.push({
      id: trade.id,
      position: trade.position,
      result: trade.result,
      entryPrice: trade.entry,
      exitPrice: trade.exit,
      startIndex,
      endIndex,
    });
  }
  return segments;
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
  const tradeFieldIndexes = backtestTradeFieldIndexes(headers);

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
    if (tradeFieldIndexes.length > 0) {
      const trade = parseBacktestTrade(row, tradeFieldIndexes);
      if (trade.id !== undefined) candle.backtestTrade = trade;
    }
    records.push(candle);
  }

  if (records.length === 0) {
    throw new Error(`No usable candle rows were found for ${entryTf}.`);
  }

  const endpointTimes = new Set();
  for (const record of records) {
    const trade = record.backtestTrade;
    if (!trade) continue;
    endpointTimes.add(record.time);
    if (Number.isFinite(trade.openTime)) endpointTimes.add(trade.openTime);
    if (Number.isFinite(trade.closeTime)) endpointTimes.add(trade.closeTime);
  }
  return collapseEntryCandles(records, endpointTimes);
}
