/** Pure report and trade-log transformations shared by result components. */
export const TRADE_COLUMN_ORDER = [
  "position",
  "entry",
  "exit",
  "sl",
  "tp",
  "open_time",
  "close_time",
  "result",
  "pnl",
  "pnl_dollar",
  "pnl_currency",
  "balance_before",
  "balance_after",
  "session",
  "day",
  "skipped",
  "skip_reason",
];

export const DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const SESSION_ORDER = ["asian", "london", "london_newyork_overlap", "newyork", "off_session"];

export function parseFormattedNumber(value) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  if (value === "Infinity") return Number.POSITIVE_INFINITY;
  if (value === "-Infinity") return Number.NEGATIVE_INFINITY;
  const normalized = value.replaceAll(",", "").replace(/[^0-9eE+.-]/g, "");
  if (!normalized) return null;
  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}

export function flattenResults(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("result.json must contain an object keyed by symbol.");
  }

  const results = [];
  for (const [symbol, entry] of Object.entries(payload)) {
    const entries = Array.isArray(entry) ? entry : [entry];
    entries.forEach((entry, index) => {
      if (!entry || typeof entry !== "object") return;
      const report = entry.report && typeof entry.report === "object" ? entry.report : {};
      results.push({
        key: JSON.stringify([symbol, entry.name ?? index]),
        symbol,
        name: String(entry.name ?? `Strategy ${index + 1}`),
        report,
        trades: Array.isArray(report.trade_log) ? report.trade_log.filter((trade) => trade && typeof trade === "object") : [],
      });
    });
  }
  return results;
}

export function orderedTradeColumns(trades) {
  const present = new Set();
  for (const trade of trades) Object.keys(trade).forEach((column) => present.add(column));
  const columns = TRADE_COLUMN_ORDER.filter((column) => present.has(column));
  for (const trade of trades) {
    for (const column of Object.keys(trade)) {
      if (!columns.includes(column)) columns.push(column);
    }
  }
  return columns;
}

export function chronologicalTrades(trades) {
  return trades
    .map((trade, originalIndex) => {
      const timestamp = Date.parse(trade.close_time);
      return { trade, originalIndex, timestamp: Number.isFinite(timestamp) ? timestamp : Number.POSITIVE_INFINITY };
    })
    .sort((left, right) => left.timestamp - right.timestamp || left.originalIndex - right.originalIndex)
    .map((entry) => entry.trade);
}

function pointColor(trade) {
  if (trade.skipped === true) return "#a3a3a3";
  if (trade.result === "win") return "#22c55e";
  if (trade.result === "loss") return "#ef4444";
  return "#f59e0b";
}

export function buildBalanceSeries(report, trades) {
  const startingBalance = parseFormattedNumber(report.starting_balance) ?? 0;
  const currency = String(report.currency ?? "USD").toUpperCase();
  const sortedTrades = chronologicalTrades(trades);
  const points = [{ x: 0, y: startingBalance, isInitial: true, color: "#60a5fa" }];
  let runningBalance = startingBalance;

  sortedTrades.forEach((trade, index) => {
    if (currency === "USD") {
      const storedBalance = parseFormattedNumber(trade.balance_after);
      const pnl = parseFormattedNumber(trade.pnl_dollar) ?? 0;
      runningBalance = storedBalance ?? runningBalance + pnl;
    } else {
      runningBalance += parseFormattedNumber(trade.pnl_currency) ?? 0;
    }
    points.push({
      x: index + 1,
      y: runningBalance,
      color: pointColor(trade),
      trade,
    });
  });

  const expectedFinalBalance = parseFormattedNumber(report.final_balance);
  const actualFinalBalance = points.at(-1)?.y ?? startingBalance;
  const reconciles = expectedFinalBalance === null
    || !Number.isFinite(expectedFinalBalance)
    || Math.abs(actualFinalBalance - expectedFinalBalance) <= 0.02;

  return { currency, startingBalance, points, reconciles, expectedFinalBalance, actualFinalBalance };
}

export function buildDrawdownSeries(balancePoints) {
  let peak = Number.NEGATIVE_INFINITY;
  return balancePoints.map((point) => {
    peak = Math.max(peak, point.y);
    const drawdown = peak > 0 ? ((point.y - peak) / peak) * 100 : 0;
    return { x: point.x, y: drawdown, trade: point.trade, isInitial: point.isInitial };
  });
}

export function breakdownRows(breakdown, preferredOrder = []) {
  if (!breakdown || typeof breakdown !== "object" || Array.isArray(breakdown)) return [];
  const entries = Object.entries(breakdown);
  const rank = new Map(preferredOrder.map((name, index) => [name, index]));
  return entries.sort(([left], [right]) => {
    const leftRank = rank.get(left) ?? preferredOrder.length;
    const rightRank = rank.get(right) ?? preferredOrder.length;
    return leftRank - rightRank || left.localeCompare(right);
  });
}

export function filterAndSortTrades(trades, columns, query, sortColumn, sortDirection = "asc") {
  const normalizedQuery = String(query ?? "").trim().toLocaleLowerCase();
  const filtered = normalizedQuery
    ? trades.filter((trade) => columns.some((column) => String(trade[column] ?? "").toLocaleLowerCase().includes(normalizedQuery)))
    : [...trades];
  if (!sortColumn) return filtered;

  const direction = sortDirection === "desc" ? -1 : 1;
  return filtered
    .map((trade, index) => ({ trade, index }))
    .sort((left, right) => {
      const a = left.trade[sortColumn];
      const b = right.trade[sortColumn];
      const aNumber = parseFormattedNumber(a);
      const bNumber = parseFormattedNumber(b);
      let comparison;
      if (aNumber !== null && bNumber !== null) comparison = aNumber - bNumber;
      else comparison = String(a ?? "").localeCompare(String(b ?? ""), undefined, { numeric: true });
      return comparison * direction || left.index - right.index;
    })
    .map((entry) => entry.trade);
}
