import { fetchText } from "./fetch-resource.js";
import { chunkCsvText } from "../lib/csv-records.js";

const CANDLES_PER_CHUNK = 1000;
const csvCache = new Map();

function subscribe(entry, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException("The operation was aborted.", "AbortError"));
  entry.consumers += 1;
  return new Promise((resolve, reject) => {
    let finished = false;
    const release = () => {
      if (finished) return;
      finished = true;
      signal?.removeEventListener("abort", abort);
      entry.consumers -= 1;
    };
    const abort = () => {
      release();
      if (!entry.settled && entry.consumers === 0) {
        entry.controller.abort();
        if (csvCache.get(entry.url) === entry) csvCache.delete(entry.url);
      }
      reject(new DOMException("The operation was aborted.", "AbortError"));
    };
    signal?.addEventListener("abort", abort, { once: true });
    entry.promise.then(
      (value) => { release(); resolve(value); },
      (error) => { release(); reject(error); },
    );
  });
}

/** Fetch a CSV URL once per session and retain its parsed, chronological chunks in memory. */
export function loadCsvDataset(csvUrl, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException("The operation was aborted.", "AbortError"));
  let entry = csvCache.get(csvUrl);
  if (!entry) {
    entry = { url: csvUrl, consumers: 0, settled: false, controller: new AbortController() };
    entry.promise = fetchText(csvUrl, entry.controller.signal)
      .then((text) => ({ text, chunks: chunkCsvText(text, CANDLES_PER_CHUNK) }))
      .then((dataset) => {
        entry.settled = true;
        if (csvCache.get(csvUrl) === entry) csvCache.set(csvUrl, { dataset });
        return dataset;
      })
      .catch((error) => {
        entry.settled = true;
        if (csvCache.get(csvUrl) === entry) csvCache.delete(csvUrl);
        throw error;
      });
    csvCache.set(csvUrl, entry);
  }
  if (entry.dataset) return Promise.resolve(entry.dataset);
  return subscribe(entry, signal);
}

// Shared by CSV resource consumers such as the results timeline and market chart.
export async function fetchCachedCsvText(csvUrl, signal) {
  return (await loadCsvDataset(csvUrl, signal)).text;
}

export function clearCsvDatasetCache() {
  csvCache.clear();
}
