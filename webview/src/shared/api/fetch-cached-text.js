import { fetchText } from "./fetch-resource.js";

const textCache = new Map();

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
        if (textCache.get(entry.url) === entry) textCache.delete(entry.url);
      }
      reject(new DOMException("The operation was aborted.", "AbortError"));
    };
    signal?.addEventListener("abort", abort, { once: true });
    entry.promise.then(
      (text) => { release(); resolve(text); },
      (error) => { release(); reject(error); },
    );
  });
}

/** Share a URL's successful text response and any in-flight request for this app session. */
export function fetchCachedText(url, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException("The operation was aborted.", "AbortError"));
  let entry = textCache.get(url);
  if (!entry) {
    entry = { url, consumers: 0, settled: false, controller: new AbortController() };
    entry.promise = fetchText(url, entry.controller.signal)
      .then((text) => {
        entry.settled = true;
        if (textCache.get(url) === entry) textCache.set(url, { text });
        return text;
      })
      .catch((error) => {
        entry.settled = true;
        if (textCache.get(url) === entry) textCache.delete(url);
        throw error;
      });
    textCache.set(url, entry);
  }
  if (entry.text !== undefined) return Promise.resolve(entry.text);
  return subscribe(entry, signal);
}

export function clearCachedText() {
  textCache.clear();
}
