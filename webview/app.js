import { QFChart } from "@qfo/qfchart";
import { convertMarketData } from "./market-data.js";
import { buildIndicator, chartAddOptions, parseIndicatorConfig } from "./indicator-plots.js";

const POLL_INTERVAL_MS = 2000;

const DEFAULT_ZOOM_START_PERCENT = 75;

function showMessage(element, message) {
  element.textContent = message;
  element.hidden = !message;
}

async function fetchText(path) {
  const separator = path.includes("?") ? "&" : "?";
  const response = await fetch(`${path}${separator}t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}.`);
  return response.text();
}

async function initialize() {
  const chartElement = document.querySelector("#chart");
  const initError = document.querySelector("#init-error");
  let chart;
  let entryTf;
  let indicatorConfig;
  let lastCsvText;
  let refreshing = false;
  let addedIndicatorIds = [];

  try {
    const config = JSON.parse(await fetchText("config.json"));
    entryTf = config.entry_tf;
    if (typeof entryTf !== "string" || !entryTf.trim()) {
      throw new Error("config.json must contain a non-empty entry_tf value.");
    }
    indicatorConfig = parseIndicatorConfig(config.indicators);
    chart = new QFChart(chartElement, {
      title: `XAUUSD ${entryTf}`,
      databox: { position: "right" },
      dataZoom: { start: DEFAULT_ZOOM_START_PERCENT, end: 100 },
    });
    window.addEventListener("resize", () => chart.resize?.());
  } catch (error) {
    showMessage(initError, `Chart initialization failed: ${error.message ?? String(error)}`);
    return;
  }

  function renderIndicators(records) {
    for (const id of addedIndicatorIds) {
      chart.removeIndicator(id);
    }
    addedIndicatorIds = [];
    const usedIds = new Set();
    let rendered = 0;
    for (const entry of indicatorConfig) {
      const built = buildIndicator(records, entry, usedIds, entryTf);
      if (!built) continue;
      const { id, plots, addOptions } = built;
      const hasData = Object.values(plots).some((plot) => plot.data.length > 0);
      if (!hasData) continue;
      chart.addIndicator(id, plots, chartAddOptions(addOptions));
      addedIndicatorIds.push(id);
      rendered += 1;
    }
    return rendered;
  }

  async function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      const csvText = await fetchText("df.csv");
      if (csvText !== lastCsvText) {
        const allColumns = indicatorConfig.flatMap((entry) => entry.columns);
        const records = convertMarketData(csvText, entryTf, allColumns);
        chart.setMarketData(records);
        renderIndicators(records);
        lastCsvText = csvText;
      }
    } catch (error) {
      console.error(`Data refresh failed; showing last valid data. ${error.message ?? String(error)}`);
    } finally {
      refreshing = false;
    }
  }

  await refresh();
  window.setInterval(refresh, POLL_INTERVAL_MS);
}

initialize();
