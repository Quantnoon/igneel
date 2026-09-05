import {
  DAY_ORDER,
  SESSION_ORDER,
  breakdownRows,
  buildBalanceSeries,
  buildDrawdownSeries,
} from "./lib/backtest-results-data.js";
import { displayValue, escapeHtml, formatMoney, formatTimestamp, humanize } from "../../shared/lib/formatters.js";

function commonOptions() {
  return {
    chart: {
      animation: false,
      backgroundColor: "transparent",
      spacing: [20, 16, 12, 12],
      style: { fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif" },
    },
    title: { style: { color: "#fafafa", fontSize: "14px", fontWeight: "600" } },
    xAxis: { labels: { style: { color: "#a3a3a3" } }, lineColor: "#404040", tickColor: "#404040" },
    yAxis: { title: { style: { color: "#a3a3a3" } }, labels: { style: { color: "#a3a3a3" } }, gridLineColor: "#262626" },
    legend: { itemStyle: { color: "#d4d4d4", fontWeight: "500" }, itemHoverStyle: { color: "#fafafa" } },
    tooltip: { backgroundColor: "#171717", borderColor: "#404040", style: { color: "#fafafa" } },
    credits: { enabled: false },
    exporting: { enabled: false },
  };
}

export function buildBalanceChart(report, trades) {
  const balance = buildBalanceSeries(report, trades);
  const money = (value) => formatMoney(value, balance.currency);
  const options = {
    ...commonOptions(),
    title: { ...commonOptions().title, text: "Account Balance Growth" },
    xAxis: { ...commonOptions().xAxis, title: { text: "Trade #", style: { color: "#a3a3a3" } } },
    yAxis: {
      ...commonOptions().yAxis,
      title: { text: `Balance (${balance.currency})`, style: { color: "#a3a3a3" } },
      labels: { style: { color: "#a3a3a3" }, formatter() { return money(this.value); } },
      plotLines: [{
        value: balance.startingBalance,
        color: "#737373",
        dashStyle: "Dash",
        width: 1,
        label: { text: "Starting balance", style: { color: "#a3a3a3" } },
      }],
    },
    tooltip: {
      ...commonOptions().tooltip,
      useHTML: true,
      formatter() {
        const point = this.point;
        if (point.isInitial) return `<b>Starting balance</b><br>${escapeHtml(money(point.y))}`;
        const trade = point.trade ?? {};
        const pnl = balance.currency === "USD" ? trade.pnl_dollar : trade.pnl_currency;
        return `<b>Trade #${point.x}</b><br>Balance: ${escapeHtml(money(point.y))}<br>Position: ${escapeHtml(displayValue(trade.position))}<br>Result: ${escapeHtml(displayValue(trade.result))}<br>P&L: ${escapeHtml(displayValue(pnl))}<br>Open: ${escapeHtml(formatTimestamp(trade.open_time))}<br>Close: ${escapeHtml(formatTimestamp(trade.close_time))}<br>Skipped: ${escapeHtml(displayValue(trade.skipped))}${trade.skip_reason ? `<br>Reason: ${escapeHtml(trade.skip_reason)}` : ""}`;
      },
    },
    series: [{
      name: "Balance",
      type: "area",
      color: "#60a5fa",
      fillColor: {
        linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
        stops: [
          [0, "rgba(96, 165, 250, 0.32)"],
          [1, "rgba(96, 165, 250, 0.02)"],
        ],
      },
      threshold: null,
      data: balance.points,
      marker: { enabled: true, radius: 3 },
      lineWidth: 2,
    }],
  };
  return { balance, options };
}

export function buildDrawdownChart(balance) {
  return {
    ...commonOptions(),
    title: { ...commonOptions().title, text: "Drawdown" },
    xAxis: { ...commonOptions().xAxis, title: { text: "Trade #", style: { color: "#a3a3a3" } } },
    yAxis: { ...commonOptions().yAxis, title: { text: "Drawdown (%)", style: { color: "#a3a3a3" } }, max: 0, labels: { format: "{value:.1f}%", style: { color: "#a3a3a3" } } },
    tooltip: { ...commonOptions().tooltip, pointFormat: "Trade #{point.x}<br><b>{point.y:.2f}%</b>" },
    series: [{ name: "Drawdown", type: "area", data: buildDrawdownSeries(balance.points), color: "#ef4444", fillOpacity: 0.2, threshold: 0 }],
  };
}

export function buildBreakdownChart(title, breakdown, order) {
  const rows = breakdownRows(breakdown, order);
  return {
    ...commonOptions(),
    title: { ...commonOptions().title, text: title },
    xAxis: { ...commonOptions().xAxis, categories: rows.map(([name]) => humanize(name)) },
    yAxis: [
      { ...commonOptions().yAxis, title: { text: "Trades", style: { color: "#a3a3a3" } }, min: 0 },
      { ...commonOptions().yAxis, title: { text: "P&L (USD)", style: { color: "#a3a3a3" } }, opposite: true },
    ],
    tooltip: { ...commonOptions().tooltip, shared: true },
    plotOptions: { column: { stacking: "normal" } },
    series: [
      { name: "Wins", type: "column", color: "#22c55e", data: rows.map(([, values]) => Number(values?.wins) || 0) },
      { name: "Losses", type: "column", color: "#ef4444", data: rows.map(([, values]) => Number(values?.losses) || 0) },
      { name: "P&L", type: "spline", yAxis: 1, color: "#60a5fa", data: rows.map(([, values]) => Number(values?.pnl_dollar) || 0) },
    ],
  };
}

export function buildSkipChart(breakdown) {
  const rows = breakdownRows(breakdown);
  if (!rows.length) return null;
  return {
    ...commonOptions(),
    chart: { ...commonOptions().chart, type: "bar" },
    title: { ...commonOptions().title, text: "Skipped Trades" },
    xAxis: { ...commonOptions().xAxis, categories: rows.map(([reason]) => humanize(reason)) },
    yAxis: { ...commonOptions().yAxis, title: { text: "Trades", style: { color: "#a3a3a3" } }, allowDecimals: false, min: 0 },
    legend: { enabled: false },
    series: [{ name: "Skipped", color: "#f59e0b", data: rows.map(([, count]) => Number(count) || 0) }],
  };
}

export const BREAKDOWN_CONFIG = {
  day: { title: "Performance by Day", order: DAY_ORDER },
  session: { title: "Performance by Session", order: SESSION_ORDER },
};
