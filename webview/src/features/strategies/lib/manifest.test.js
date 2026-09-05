import assert from "node:assert/strict";
import { test } from "vitest";

import { MANIFEST_PATH, activeEnvironment, findStrategy, isAccessible, parseStrategyManifest } from "./manifest.js";

const strategy = {
  name: "strategies/support_resistance",
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
  assert.deepEqual(entry.resources, {
    ...strategy.env.development,
    df: strategy.env.development.df,
  });
  assert.deepEqual(entry.missingResources, []);
  assert.ok(isAccessible(entry));
  assert.equal(findStrategy([entry], "support_resistance"), entry);
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
