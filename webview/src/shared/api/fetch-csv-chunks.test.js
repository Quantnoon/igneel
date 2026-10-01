import assert from "node:assert/strict";
import { afterEach, test, vi } from "vitest";

import { loadInitialCsvChunk, loadOlderCsvChunk } from "./fetch-csv-chunks.js";

afterEach(() => vi.unstubAllGlobals());

function response(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, text: () => Promise.resolve(body) };
}

test("loads the newest chunk first and requests older chunks by manifest order", async () => {
  globalThis.fetch = vi.fn((url) => {
    if (String(url).includes("index.json")) return Promise.resolve(response('{"chunks":["chunk-000001.csv","chunk-000000.csv"]}'));
    return Promise.resolve(response(String(url).includes("000001") ? "newest" : "older"));
  });
  const initial = await loadInitialCsvChunk("strategies/demo/EURUSD_df.csv");
  assert.equal(initial.csvText, "newest");
  assert.deepEqual(initial.chunks, ["chunk-000001.csv", "chunk-000000.csv"]);
  assert.equal(await loadOlderCsvChunk("strategies/demo/EURUSD_df.csv", initial.chunks, initial.nextChunkIndex), "older");
});

test("falls back to the monolithic CSV when chunk resources are missing or SPA-rewritten", async () => {
  globalThis.fetch = vi.fn((url) => Promise.resolve(
    String(url).includes("index.json") ? response("Not found", 404) : response("full csv"),
  ));
  assert.deepEqual(await loadInitialCsvChunk("df.csv"), { csvText: "full csv", chunks: null, nextChunkIndex: null });

  globalThis.fetch = vi.fn((url) => Promise.resolve(
    String(url).includes("index.json") ? response("<!doctype html><html></html>") : response("full csv"),
  ));
  assert.equal((await loadInitialCsvChunk("df.csv")).csvText, "full csv");
});
