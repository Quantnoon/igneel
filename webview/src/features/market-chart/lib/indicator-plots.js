import { interpolateIndicatorPoints, rawIndicatorPoints, stepIndicatorPoints } from "../../../shared/lib/market-data.js";

const INDICATOR_COLORS = {
  EMA: ["#2962FF", "#FF6D00"],
  SMA: ["#26A69A", "#AB47BC"],
  BBANDS: ["#EC407A", "#FFB300", "#EC407A"],
  VOLATILITY_REGIME: ["#AB47BC"],
};

const CANDLESTICK_PATTERN_COLORS = {
  bullish: "#26A69A",
  bearish: "#EF5350",
};

const ZONES = {
  SUPPLY_ZONE: {
    id: "supply-zone",
    lowStem: "supply_low",
    highStem: "supply_high",
    color: "#E53935",
    fillColor: "rgba(229, 57, 53, 0.18)",
  },
  DEMAND_ZONE: {
    id: "demand-zone",
    lowStem: "demand_low",
    highStem: "demand_high",
    color: "#43A047",
    fillColor: "rgba(67, 160, 71, 0.18)",
  },
  SUPPORT_ZONE: {
    id: "support-zone",
    lowStem: "support_low",
    highStem: "support_high",
    color: "#43A047",
    fillColor: "rgba(67, 160, 71, 0.18)",
  },
  RESISTANCE_ZONE: {
    id: "resistance-zone",
    lowStem: "resistance_low",
    highStem: "resistance_high",
    color: "#E53935",
    fillColor: "rgba(229, 57, 53, 0.18)",
  },
  BULLISH_FVG: {
    id: "bullish-fvg",
    lowStem: "bullish_fvg_low",
    highStem: "bullish_fvg_high",
    color: "#43A047",
    fillColor: "rgba(67, 160, 71, 0.18)",
  },
  BEARISH_FVG: {
    id: "bearish-fvg",
    lowStem: "bearish_fvg_low",
    highStem: "bearish_fvg_high",
    color: "#E53935",
    fillColor: "rgba(229, 57, 53, 0.18)",
  },
};

const SESSION_LEVELS = {
  LONDON_HIGH: { id: "london-high", stem: "london_high", color: "#42A5F5" },
  LONDON_LOW: { id: "london-low", stem: "london_low", color: "#90CAF9" },
  NEWYORK_HIGH: { id: "newyork-high", stem: "newyork_high", color: "#AB47BC" },
  NEWYORK_LOW: { id: "newyork-low", stem: "newyork_low", color: "#CE93D8" },
  ASIAN_HIGH: { id: "asian-high", stem: "asian_high", color: "#FFB300" },
  ASIAN_LOW: { id: "asian-low", stem: "asian_low", color: "#FFE082" },
};

export const REGIME_PANE_HEIGHT = 8;
export const HIDDEN_OVERLAY_TITLE_COLOR = "rgba(0, 0, 0, 0)";

const REGIME_COLORS = {
  0: "#26A69A",
  1: "#FFB300",
  2: "#EF5350",
};

function isRegimeType(type) {
  return type === "VOLATILITY_REGIME";
}

function isCandlestickPattern(type) {
  return typeof type === "string" && type.startsWith("CDL");
}

function regimeColor(value) {
  return REGIME_COLORS[value] ?? "#AB47BC";
}

function indicatorColor(type, columnIndex) {
  const palette = INDICATOR_COLORS[type] ?? ["#2962FF", "#FF6D00", "#26A69A"];
  return palette[columnIndex % palette.length];
}

export function parseIndicatorConfig(indicators) {
  if (!Array.isArray(indicators)) return [];
  return indicators
    .filter((entry) => entry && typeof entry.type === "string" && Array.isArray(entry.columns))
    .map((entry) => ({ type: entry.type, columns: entry.columns.filter((column) => typeof column === "string") }));
}

export function chartAddOptions(addOptions) {
  if (!addOptions.overlay) return addOptions;
  return { ...addOptions, titleColor: HIDDEN_OVERLAY_TITLE_COLOR };
}

function uniqueIndicatorId(preferredId, entry, usedIds) {
  let id = preferredId;
  if (usedIds.has(id)) {
    const suffixMatch = entry.columns[0]?.match(/_([A-Za-z0-9]+)$/);
    if (suffixMatch) id = `${preferredId}_${suffixMatch[1]}`;
  }
  while (usedIds.has(id)) id = `${id}_2`;
  usedIds.add(id);
  return id;
}

function zoneColumn(columns, stem) {
  return columns.find((column) => column === stem || column.startsWith(`${stem}_`));
}

function buildSessionLevelPlot(records, entry, usedIds) {
  const level = SESSION_LEVELS[entry.type];
  if (!level) return null;
  const column = zoneColumn(entry.columns, level.stem);
  if (!column) return null;
  const data = stepIndicatorPoints(records, column);
  if (data.length === 0) return null;

  return {
    id: uniqueIndicatorId(level.id, entry, usedIds),
    plots: {
      [column]: {
        data,
        options: {
          style: "step",
          color: level.color,
          linewidth: 1.5,
        },
      },
    },
    addOptions: { overlay: true },
  };
}

function buildZonePlots(records, entry, usedIds) {
  const zone = ZONES[entry.type];
  if (!zone) return null;

  const lowColumn = zoneColumn(entry.columns, zone.lowStem);
  const highColumn = zoneColumn(entry.columns, zone.highStem);
  if (!lowColumn || !highColumn) return null;

  const lowData = rawIndicatorPoints(records, lowColumn);
  const highData = rawIndicatorPoints(records, highColumn);
  if (lowData.length === 0 || highData.length === 0) return null;

  const lowPlot = `${zone.id}-low`;
  const highPlot = `${zone.id}-high`;
  return {
    id: uniqueIndicatorId(zone.id, entry, usedIds),
    plots: {
      [lowPlot]: {
        data: lowData,
        options: { style: "step", color: zone.color, linewidth: 1.5 },
      },
      [highPlot]: {
        data: highData,
        options: { style: "step", color: zone.color, linewidth: 1.5 },
      },
      [`${zone.id}-fill`]: {
        data: [],
        options: { style: "fill", color: zone.fillColor, plot1: lowPlot, plot2: highPlot },
      },
    },
    addOptions: { overlay: true },
  };
}

function buildRegimePlots(records, entry, usedIds) {
  const plots = {};
  for (const [columnIndex, column] of entry.columns.entries()) {
    const data = rawIndicatorPoints(records, column).map((point) => ({
      ...point,
      options: { color: regimeColor(point.value) },
    }));
    plots[column] = {
      data,
      options: { style: "columns", color: indicatorColor(entry.type, columnIndex), histbase: 0 },
    };
  }

  return {
    id: uniqueIndicatorId(entry.type.toLowerCase(), entry, usedIds),
    plots,
    addOptions: { overlay: false, height: REGIME_PANE_HEIGHT },
  };
}

function buildPatternPlots(records, entry, usedIds) {
  const plots = {};
  let hasPoints = false;
  for (const column of entry.columns) {
    const data = rawIndicatorPoints(records, column)
      .filter((point) => point.value !== 0)
      .map((point) => {
        const bearish = point.value < 0;
        return {
          ...point,
          options: {
            shape: bearish ? "arrowdown" : "arrowup",
            location: bearish ? "abovebar" : "belowbar",
            color: CANDLESTICK_PATTERN_COLORS[bearish ? "bearish" : "bullish"],
            size: "small",
          },
        };
      });
    if (data.length > 0) hasPoints = true;
    plots[column] = {
      data,
      options: {
        style: "shape",
        shape: "arrowup",
        location: "belowbar",
        color: CANDLESTICK_PATTERN_COLORS.bullish,
        size: "small",
      },
    };
  }
  if (!hasPoints) return null;

  return {
    id: uniqueIndicatorId(entry.type.toLowerCase(), entry, usedIds),
    plots,
    addOptions: { overlay: true },
  };
}

function buildLinePlots(records, entry, usedIds, entryTf) {
  const plots = {};
  for (const [columnIndex, column] of entry.columns.entries()) {
    const data = interpolateIndicatorPoints(records, column, entryTf);
    plots[column] = {
      data,
      options: { style: "line", color: indicatorColor(entry.type, columnIndex), linewidth: 1.5 },
    };
  }

  return { id: uniqueIndicatorId(entry.type, entry, usedIds), plots, addOptions: { overlay: true } };
}

export function buildIndicator(records, entry, usedIds, entryTf) {
  if (SESSION_LEVELS[entry.type]) return buildSessionLevelPlot(records, entry, usedIds);
  if (ZONES[entry.type]) return buildZonePlots(records, entry, usedIds);
  if (isRegimeType(entry.type)) return buildRegimePlots(records, entry, usedIds);
  if (isCandlestickPattern(entry.type)) return buildPatternPlots(records, entry, usedIds);
  return buildLinePlots(records, entry, usedIds, entryTf);
}

export function indicatorSeriesColorPatches(builtIndicators) {
  if (!Array.isArray(builtIndicators)) return [];

  return builtIndicators.flatMap((built) => {
    if (!built || typeof built.id !== "string" || !built.plots) return [];
    return Object.entries(built.plots)
      .filter(([, plot]) => plot?.options?.style !== "fill" && typeof plot?.options?.color === "string")
      .map(([plotName, plot]) => ({ name: `${built.id}::${plotName}`, color: plot.options.color }));
  });
}

export function applyIndicatorSeriesColors(chart, patches) {
  if (!Array.isArray(patches) || patches.length === 0) return;

  const echarts = chart.getChart();
  const series = echarts.getOption().series;
  if (!Array.isArray(series)) return;

  const seriesByName = new Map(series.filter((entry) => typeof entry?.name === "string").map((entry) => [entry.name, entry]));
  const updates = [];
  for (const patch of patches) {
    const existing = seriesByName.get(patch?.name);
    if (!existing || typeof patch?.color !== "string") continue;
    const existingColor = Array.isArray(existing.color) ? existing.color[0] : existing.color;
    if (typeof existingColor === "string" && existingColor.toLowerCase() === patch.color.toLowerCase()) continue;
    updates.push({ name: patch.name, type: existing.type, color: patch.color });
  }

  if (updates.length > 0) echarts.setOption({ series: updates });
}
