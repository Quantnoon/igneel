import { parseIndicatorConfig } from "../../market-chart/lib/indicator-plots.js";

export function parseStrategyConfig(text) {
  let config;
  try {
    config = JSON.parse(text);
  } catch {
    throw new Error("config.json is not valid JSON.");
  }
  if (!Array.isArray(config.symbols) || config.symbols.length === 0) {
    throw new Error("config.json must contain a non-empty symbols array.");
  }
  const symbols = config.symbols.map((symbol) => String(symbol ?? "").trim());
  if (symbols.some((symbol) => !symbol)) {
    throw new Error("config.json symbols must be non-empty strings.");
  }
  if (new Set(symbols).size !== symbols.length) {
    throw new Error("config.json symbols must be unique.");
  }
  if (typeof config.entry_tf !== "string" || !config.entry_tf.trim()) {
    throw new Error("config.json must contain a non-empty entry_tf value.");
  }
  return {
    symbols,
    entryTf: config.entry_tf.trim(),
    indicators: parseIndicatorConfig(config.indicators),
  };
}
