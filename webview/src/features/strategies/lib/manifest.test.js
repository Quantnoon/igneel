import assert from "node:assert/strict";
import { test } from "vitest";

import { MANIFEST_PATH, activeEnvironment, findStrategy, isAccessible, parseStrategyManifest } from "./manifest.js";

const strategy = {
  name: "strategies/support_resistance",
  botUrls: {
    windows: "https://example.com/support-resistance-windows.ex5",
    mac: "https://example.com/support-resistance-mac.ex5",
  },
  env: {
    production: { df: [], config: "", result: "" },
    development: {
      df: [
        { name: "EURUSDm", path: "strategies/support_resistance/EURUSDm_df.csv" },
        { name: "GBPUSDm", path: "strategies/support_resistance/GBPUSDm_df.csv" },
      ],
      config: "strategies/support_resistance/config.json",
      result: "strategies/support_resistance/result.json",
    },
  },
};

test("parses new strategy resources and derives the short route name", () => {
  const [entry] = parseStrategyManifest(JSON.stringify([strategy]), "development");
  assert.equal(MANIFEST_PATH, "strategies/strategies.json");
  assert.equal(entry.name, "support_resistance");
  assert.equal(entry.resourceIdentity, "strategies/support_resistance");
  assert.deepEqual(entry.botUrls, strategy.botUrls);
  assert.deepEqual(entry.resources, {
    ...strategy.env.development,
    df: strategy.env.development.df,
  });
  assert.deepEqual(entry.missingResources, []);
  assert.ok(isAccessible(entry));
  assert.equal(findStrategy([entry], "support_resistance"), entry);
});

test("defaults missing, malformed, or blank platform download URLs to empty strings", () => {
  const [missing] = parseStrategyManifest(JSON.stringify([{ ...strategy, botUrls: undefined }]), "development");
  const [malformed] = parseStrategyManifest(JSON.stringify([{ ...strategy, botUrls: [] }]), "development");
  const [partial] = parseStrategyManifest(JSON.stringify([{ ...strategy, botUrls: { windows: "  ", mac: strategy.botUrls.mac } }]), "development");
  assert.deepEqual(missing.botUrls, { windows: "", mac: "" });
  assert.deepEqual(malformed.botUrls, { windows: "", mac: "" });
  assert.deepEqual(partial.botUrls, { windows: "", mac: strategy.botUrls.mac });
});

test("requires a strategies/<name> identity and array CSV resources", () => {
  assert.throws(() => parseStrategyManifest(JSON.stringify([{ ...strategy, name: "support-resistance" }]), "development"), /strategies\/<name>/);
  const [entry] = parseStrategyManifest(JSON.stringify([{ ...strategy, env: { development: { ...strategy.env.development, df: "df.csv" } } }]), "development");
  assert.deepEqual(entry.missingResources, ["df"]);
});

test("rejects duplicate route names and malformed manifests", () => {
  assert.throws(() => parseStrategyManifest(JSON.stringify([strategy, strategy]), "development"), /duplicated/);
  assert.throws(() => parseStrategyManifest("{ nope", "development"), /not valid JSON/);
  assert.throws(() => parseStrategyManifest("{}", "development"), /must contain an array/);
});

test("selects the requested environment", () => {
  const [entry] = parseStrategyManifest(JSON.stringify([strategy]), "production");
  assert.deepEqual(entry.missingResources, ["df", "config", "result"]);
  assert.equal(activeEnvironment(true), "development");
  assert.equal(activeEnvironment(false), "production");
});
