import { interpolateIndicatorPoints, rawIndicatorPoints } from "./market-data.js";

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
  if (ZONES[entry.type]) return buildZonePlots(records, entry, usedIds);
  if (isRegimeType(entry.type)) return buildRegimePlots(records, entry, usedIds);
  if (isCandlestickPattern(entry.type)) return buildPatternPlots(records, entry, usedIds);
  return buildLinePlots(records, entry, usedIds, entryTf);
}
