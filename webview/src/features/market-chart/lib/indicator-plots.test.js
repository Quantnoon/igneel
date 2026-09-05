import assert from "node:assert/strict";
import { test, vi } from "vitest";

import {
  HIDDEN_OVERLAY_TITLE_COLOR,
  REGIME_PANE_HEIGHT,
  buildIndicator,
  chartAddOptions,
  applyIndicatorSeriesColors,
  indicatorSeriesColorPatches,
  parseIndicatorConfig,
} from "./indicator-plots.js";

function candleRecord(time, indicatorValues = {}) {
  return { time, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10, ...indicatorValues };
}

function zoneEntry(type, lowStem, highStem) {
  return { type, columns: [`${lowStem}_H1`, `${highStem}_H1`] };
}

function zoneRecords(lowStem, highStem) {
  return [
    candleRecord(0),
    candleRecord(1, { [`${lowStem}_H1`]: 10, [`${highStem}_H1`]: 12 }),
    candleRecord(2, { [`${lowStem}_H1`]: 10, [`${highStem}_H1`]: 12 }),
    candleRecord(3),
    candleRecord(4, { [`${lowStem}_H1`]: 14, [`${highStem}_H1`]: 16 }),
  ];
}

const SESSION_FIXTURES = [
  ["LONDON_HIGH", "london_high", "#42A5F5"],
  ["LONDON_LOW", "london_low", "#90CAF9"],
  ["NEWYORK_HIGH", "newyork_high", "#AB47BC"],
  ["NEWYORK_LOW", "newyork_low", "#CE93D8"],
  ["ASIAN_HIGH", "asian_high", "#FFB300"],
  ["ASIAN_LOW", "asian_low", "#FFE082"],
];

for (const [type, stem, color] of SESSION_FIXTURES) {
  test(`${type} renders a colored step overlay`, () => {
    const column = `${stem}_H4`;
    const records = [candleRecord(0), candleRecord(1, { [column]: 10 }), candleRecord(2), candleRecord(3, { [column]: 12 })];
    const built = buildIndicator(records, { type, columns: [column] }, new Set(), "M15");

    assert.ok(built);
    assert.deepEqual(built.addOptions, { overlay: true });
    const plot = built.plots[column];
    assert.equal(plot.options.style, "step");
    assert.equal(plot.options.color, color);
    assert.equal("lineStyle" in plot.options, false);
    assert.equal("lineDash" in plot.options, false);
    assert.deepEqual(plot.data, [
      { time: 1, value: 10 },
      { time: 2, value: 10 },
      { time: 3, value: 12 },
    ]);
  });
}

test("session levels return null for missing or empty columns", () => {
  assert.equal(buildIndicator([candleRecord(0)], { type: "LONDON_HIGH", columns: [] }, new Set(), "M15"), null);
  assert.equal(buildIndicator([candleRecord(0)], { type: "LONDON_HIGH", columns: ["london_high_H4"] }, new Set(), "M15"), null);
});

test("hides main-pane overlay titles while leaving indicator panes unchanged", () => {
  const overlay = { overlay: true };
  const pane = { overlay: false, height: REGIME_PANE_HEIGHT };

  assert.deepEqual(chartAddOptions(overlay), {
    overlay: true,
    titleColor: HIDDEN_OVERLAY_TITLE_COLOR,
  });
  assert.equal(chartAddOptions(pane), pane);
});

const ZONE_FIXTURES = [
  { type: "SUPPLY_ZONE", lowStem: "supply_low", highStem: "supply_high", expectedColor: "#E53935", expectedFill: "rgba(229, 57, 53, 0.18)" },
  { type: "DEMAND_ZONE", lowStem: "demand_low", highStem: "demand_high", expectedColor: "#43A047", expectedFill: "rgba(67, 160, 71, 0.18)" },
  { type: "SUPPORT_ZONE", lowStem: "support_low", highStem: "support_high", expectedColor: "#43A047", expectedFill: "rgba(67, 160, 71, 0.18)" },
  { type: "RESISTANCE_ZONE", lowStem: "resistance_low", highStem: "resistance_high", expectedColor: "#E53935", expectedFill: "rgba(229, 57, 53, 0.18)" },
  { type: "BULLISH_FVG", lowStem: "bullish_fvg_low", highStem: "bullish_fvg_high", expectedColor: "#43A047", expectedFill: "rgba(67, 160, 71, 0.18)" },
  { type: "BEARISH_FVG", lowStem: "bearish_fvg_low", highStem: "bearish_fvg_high", expectedColor: "#E53935", expectedFill: "rgba(229, 57, 53, 0.18)" },
];

for (const { type, lowStem, highStem, expectedColor, expectedFill } of ZONE_FIXTURES) {
  test(`${type} renders ${expectedColor === "#E53935" ? "red" : "green"} step bounds as a main-pane overlay`, () => {
    const records = zoneRecords(lowStem, highStem);
    const built = buildIndicator(records, zoneEntry(type, lowStem, highStem), new Set(), "M15");

    assert.ok(built);
    assert.deepEqual(built.addOptions, { overlay: true });

    const plotNames = Object.keys(built.plots);
    assert.equal(plotNames.filter((name) => name.endsWith("-low") || name.endsWith("-high")).length, 2);
    for (const name of plotNames) {
      const plot = built.plots[name];
      if (name.endsWith("-fill")) continue;
      assert.equal(plot.options.style, "step", `${name} must be a step boundary`);
      assert.equal(plot.options.color, expectedColor);
    }

    const fill = built.plots[plotNames.find((name) => name.endsWith("-fill"))];
    assert.equal(fill.options.style, "fill");
    assert.equal(fill.options.color, expectedFill);
    assert.ok(built.plots[fill.options.plot1], "fill plot1 must reference an existing plot");
    assert.ok(built.plots[fill.options.plot2], "fill plot2 must reference an existing plot");
    assert.match(fill.options.plot1, /-low$/);
    assert.match(fill.options.plot2, /-high$/);
  });
}

test("zones return null when boundary columns are missing or empty", () => {
  assert.equal(buildIndicator([candleRecord(0)], { type: "SUPPLY_ZONE", columns: ["supply_low_H1"] }, new Set(), "M15"), null);
  assert.equal(
    buildIndicator([candleRecord(0)], { type: "SUPPLY_ZONE", columns: ["supply_low_H1", "supply_high_H1"] }, new Set(), "M15"),
    null,
  );
});

test("indicator series color patches include colored non-fill plots", () => {
  const session = buildIndicator(
    [candleRecord(0), candleRecord(1, { london_high_H4: 10 })],
    { type: "LONDON_HIGH", columns: ["london_high_H4"] },
    new Set(),
    "M15",
  );
  const zone = buildIndicator(
    zoneRecords("support_low", "support_high"),
    zoneEntry("SUPPORT_ZONE", "support_low", "support_high"),
    new Set(),
    "M15",
  );
  const resistance = buildIndicator(
    zoneRecords("resistance_low", "resistance_high"),
    zoneEntry("RESISTANCE_ZONE", "resistance_low", "resistance_high"),
    new Set(),
    "M15",
  );
  const ema = buildIndicator(
    [candleRecord(0, { ema_14_H1: 1 })],
    { type: "EMA", columns: ["ema_14_H1"] },
    new Set(),
    "M15",
  );

  assert.deepEqual(indicatorSeriesColorPatches([session, zone, resistance, ema]), [
    { name: "london-high::london_high_H4", color: "#42A5F5" },
    { name: "support-zone::support-zone-low", color: "#43A047" },
    { name: "support-zone::support-zone-high", color: "#43A047" },
    { name: "resistance-zone::resistance-zone-low", color: "#E53935" },
    { name: "resistance-zone::resistance-zone-high", color: "#E53935" },
    { name: "EMA::ema_14_H1", color: "#2962FF" },
  ]);
});

test("indicator series color patches are empty for invalid or uncolored indicators", () => {
  assert.deepEqual(indicatorSeriesColorPatches([null, { id: "empty", plots: {} }, { id: "fill", plots: { area: { options: { style: "fill", color: "#fff" } } } }]), []);
  assert.deepEqual(indicatorSeriesColorPatches(undefined), []);
});

test("applyIndicatorSeriesColors updates matching series with their existing types", () => {
  const setOption = vi.fn();
  const chart = {
    getChart: () => ({
      getOption: () => ({ series: [
        { name: "london-high::london_high_H4", type: "custom", color: ["#999999"] },
        { name: "EMA::ema_14_H1", type: "line", color: "#2962ff" },
      ] }),
      setOption,
    }),
  };

  applyIndicatorSeriesColors(chart, [
    { name: "london-high::london_high_H4", color: "#42A5F5" },
    { name: "EMA::ema_14_H1", color: "#2962FF" },
    { name: "missing::plot", color: "#fff" },
  ]);

  assert.deepEqual(setOption.mock.calls, [[{ series: [{ name: "london-high::london_high_H4", type: "custom", color: "#42A5F5" }] }]]);
});

test("applyIndicatorSeriesColors does not set options when no colors need changing", () => {
  const setOption = vi.fn();
  const chart = {
    getChart: () => ({
      getOption: () => ({ series: [{ name: "EMA::ema_14_H1", type: "line", color: ["#2962FF"] }] }),
      setOption,
    }),
  };

  applyIndicatorSeriesColors(chart, [{ name: "EMA::ema_14_H1", color: "#2962ff" }]);
  applyIndicatorSeriesColors(chart, [{ name: "missing::plot", color: "#fff" }]);
  applyIndicatorSeriesColors(chart, []);

  assert.deepEqual(setOption.mock.calls, []);
});

test("FVGs return null when boundary columns are missing or empty", () => {
  assert.equal(buildIndicator([candleRecord(0)], { type: "BULLISH_FVG", columns: ["bullish_fvg_low_H1"] }, new Set(), "M15"), null);
  assert.equal(buildIndicator([candleRecord(0)], { type: "BEARISH_FVG", columns: ["bearish_fvg_low_H1"] }, new Set(), "M15"), null);
  assert.equal(
    buildIndicator([candleRecord(0)], { type: "BULLISH_FVG", columns: ["bullish_fvg_low_H1", "bullish_fvg_high_H1"] }, new Set(), "M15"),
    null,
  );
  assert.equal(
    buildIndicator([candleRecord(0)], { type: "BEARISH_FVG", columns: ["bearish_fvg_low_H1", "bearish_fvg_high_H1"] }, new Set(), "M15"),
    null,
  );
});

test("VOLATILITY_REGIME renders a per-state colored histogram in a separate compact pane", () => {
  const records = [
    candleRecord(0, { volatility_regime_H1: 0 }),
    candleRecord(1, { volatility_regime_H1: 0 }),
    candleRecord(2),
    candleRecord(3, { volatility_regime_H1: 1 }),
    candleRecord(4, { volatility_regime_H1: 2 }),
  ];
  const built = buildIndicator(records, { type: "VOLATILITY_REGIME", columns: ["volatility_regime_H1"] }, new Set(), "M15");

  assert.ok(built);
  assert.deepEqual(built.addOptions, { overlay: false, height: REGIME_PANE_HEIGHT });
  assert.equal(REGIME_PANE_HEIGHT, 8);

  const plot = built.plots.volatility_regime_H1;
  assert.equal(plot.options.style, "columns");
  assert.equal(plot.options.histbase, 0);
  assert.deepEqual(
    plot.data.map((point) => ({ time: point.time, value: point.value, color: point.options.color })),
    [
      { time: 0, value: 0, color: "#26A69A" },
      { time: 1, value: 0, color: "#26A69A" },
      { time: 3, value: 1, color: "#FFB300" },
      { time: 4, value: 2, color: "#EF5350" },
    ],
  );
});

test("candlestick patterns render directional shape markers on the main pane", () => {
  const records = [
    candleRecord(0, { cdlhammer_H1: 100 }),
    candleRecord(1, { cdlshootingstar_H1: -100 }),
  ];

  const hammer = buildIndicator(records, { type: "CDLHAMMER", columns: ["cdlhammer_H1"] }, new Set(), "M15");
  assert.ok(hammer);
  assert.deepEqual(hammer.addOptions, { overlay: true });
  assert.equal(hammer.id, "cdlhammer");
  const hammerPlot = hammer.plots.cdlhammer_H1;
  assert.equal(hammerPlot.options.style, "shape");
  assert.deepEqual(hammerPlot.data, [
    {
      time: 0,
      value: 100,
      options: { shape: "arrowup", location: "belowbar", color: "#26A69A", size: "small" },
    },
  ]);

  const star = buildIndicator(records, { type: "CDLSHOOTINGSTAR", columns: ["cdlshootingstar_H1"] }, new Set(), "M15");
  assert.ok(star);
  assert.deepEqual(star.plots.cdlshootingstar_H1.data, [
    {
      time: 1,
      value: -100,
      options: { shape: "arrowdown", location: "abovebar", color: "#EF5350", size: "small" },
    },
  ]);
});

test("candlestick patterns skip zero and non-finite values", () => {
  const records = [
    candleRecord(0, { cdlhammer_H1: 0 }),
    candleRecord(1, { cdlhammer_H1: 100 }),
    candleRecord(2, { cdlhammer_H1: 0 }),
    candleRecord(3, { cdlhammer_H1: NaN }),
  ];
  const built = buildIndicator(records, { type: "CDLHAMMER", columns: ["cdlhammer_H1"] }, new Set(), "M15");

  assert.ok(built);
  assert.deepEqual(
    built.plots.cdlhammer_H1.data.map((point) => ({ time: point.time, value: point.value })),
    [{ time: 1, value: 100 }],
  );
});

test("candlestick patterns return null when no signals fire", () => {
  const records = [
    candleRecord(0, { cdlhammer_H1: 0 }),
    candleRecord(1, { cdlhammer_H1: NaN }),
    candleRecord(2, { cdlhammer_H1: 0 }),
  ];

  assert.equal(buildIndicator(records, { type: "CDLHAMMER", columns: ["cdlhammer_H1"] }, new Set(), "M15"), null);
});

test("candlestick patterns receive unique ids for repeated types", () => {
  const usedIds = new Set();
  const records = [
    candleRecord(0, { cdlhammer_H1: 100 }),
    candleRecord(1, { cdlhammer_M15: 100, cdlengulfing_H1: 100 }),
  ];

  const first = buildIndicator(records, { type: "CDLHAMMER", columns: ["cdlhammer_H1"] }, usedIds, "M15");
  const second = buildIndicator(records, { type: "CDLHAMMER", columns: ["cdlhammer_M15"] }, usedIds, "M15");
  const engulfing = buildIndicator(records, { type: "CDLENGULFING", columns: ["cdlengulfing_H1"] }, usedIds, "M15");

  assert.equal(first.id, "cdlhammer");
  assert.equal(second.id, "cdlhammer_M15");
  assert.equal(engulfing.id, "cdlengulfing");
});

test("generic indicators remain interpolated line overlays on the main pane", () => {
  const records = [
    candleRecord(0),
    candleRecord(1, { ema_14_H1: 1 }),
    candleRecord(2),
    candleRecord(3, { ema_14_H1: 3 }),
    candleRecord(4, { ema_14_H1: 3 }),
  ];
  const built = buildIndicator(records, { type: "EMA", columns: ["ema_14_H1"] }, new Set(), "M15");

  assert.ok(built);
  assert.deepEqual(built.addOptions, { overlay: true });
  const plot = built.plots.ema_14_H1;
  assert.equal(plot.options.style, "line");

  const values = new Map(plot.data.map((point) => [point.time, point.value]));
  assert.equal(values.get(1), 1);
  assert.ok(Math.abs(values.get(2) - 2) < 1e-9, "intermediate candle must be interpolated");
  assert.equal(values.get(3), 3);
  assert.equal(values.get(4), 3);
});

test("duplicate indicator types receive unique ids", () => {
  const usedIds = new Set();
  const records = zoneRecords("supply_low", "supply_high");
  const first = buildIndicator(records, zoneEntry("SUPPLY_ZONE", "supply_low", "supply_high"), usedIds, "M15");
  const second = buildIndicator(records, zoneEntry("SUPPLY_ZONE", "supply_low", "supply_high"), usedIds, "M15");

  assert.equal(first.id, "supply-zone");
  assert.equal(second.id, "supply-zone_H1");
});

test("parseIndicatorConfig filters malformed entries and non-string columns", () => {
  const parsed = parseIndicatorConfig([
    { type: "EMA", columns: ["ema_14_H1", 42, null] },
    { type: "SUPPLY_ZONE" },
    null,
    "EMA",
    { columns: ["ema_14_H1"] },
  ]);

  assert.deepEqual(parsed, [{ type: "EMA", columns: ["ema_14_H1"] }]);
  assert.deepEqual(parseIndicatorConfig(undefined), []);
});
