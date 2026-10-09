import assert from "node:assert/strict";
import { afterEach, test, vi } from "vitest";

import { clearCsvDatasetCache, loadCsvDataset } from "./fetch-csv-chunks.js";

afterEach(() => {
  clearCsvDatasetCache();
  vi.unstubAllGlobals();
});

function response(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, text: () => Promise.resolve(body) };
}

test("fetches once and returns chronological chunks with the newest chunk last", async () => {
  const csv = `time,value\n${Array.from({ length: 2001 }, (_, index) => `${index},row-${index}`).join("\n")}`;
  globalThis.fetch = vi.fn(() => Promise.resolve(response(csv)));
  const dataset = await loadCsvDataset("cloudinary.csv");
  assert.equal(dataset.chunks.length, 3);
  assert.equal(dataset.chunks[0].split("\n")[1], "0,row-0");
  assert.equal(dataset.chunks.at(-1).split("\n")[1], "2000,row-2000");
  assert.equal((await loadCsvDataset("cloudinary.csv")).text, csv);
  assert.equal(globalThis.fetch.mock.calls.length, 1);
});

test("shares an in-flight load, but keeps different URLs in separate cache entries", async () => {
  globalThis.fetch = vi.fn((url) => Promise.resolve(response(`time,value\n${url},one`)));
  const [first, second] = await Promise.all([
    loadCsvDataset("first.csv"),
    loadCsvDataset("first.csv"),
  ]);
  const other = await loadCsvDataset("second.csv");
  assert.equal(first, second);
  assert.notEqual(first, other);
  assert.equal(globalThis.fetch.mock.calls.length, 2);
});

test("does not retain failed requests and allows retry", async () => {
  globalThis.fetch = vi.fn()
    .mockResolvedValueOnce(response("unavailable", 503))
    .mockResolvedValueOnce(response("time,value\n1,ok"));
  await assert.rejects(loadCsvDataset("retry.csv"), /HTTP 503/);
  assert.equal((await loadCsvDataset("retry.csv")).text, "time,value\n1,ok");
  assert.equal(globalThis.fetch.mock.calls.length, 2);
});

test("an aborted consumer stops waiting without breaking a shared load", async () => {
  let resolveResponse;
  globalThis.fetch = vi.fn(() => new Promise((resolve) => { resolveResponse = resolve; }));
  const controller = new AbortController();
  const abortedLoad = loadCsvDataset("shared.csv", controller.signal);
  const otherLoad = loadCsvDataset("shared.csv");
  controller.abort();
  await assert.rejects(abortedLoad, { name: "AbortError" });
  resolveResponse(response("time,value\n1,ok"));
  assert.equal((await otherLoad).text, "time,value\n1,ok");
  assert.equal(globalThis.fetch.mock.calls.length, 1);
});

test("aborts and evicts an in-flight request when its last consumer leaves", async () => {
  let firstSignal;
  globalThis.fetch = vi.fn((url, { signal }) => {
    if (globalThis.fetch.mock.calls.length === 1) {
      firstSignal = signal;
      return new Promise((resolve, reject) => signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true }));
    }
    return Promise.resolve(response("time,value\n1,retried"));
  });
  const controller = new AbortController();
  const abandoned = loadCsvDataset("aborted.csv", controller.signal);
  controller.abort();
  await assert.rejects(abandoned, { name: "AbortError" });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(firstSignal.aborted, true);
  assert.equal((await loadCsvDataset("aborted.csv")).text, "time,value\n1,retried");
  assert.equal(globalThis.fetch.mock.calls.length, 2);
});
