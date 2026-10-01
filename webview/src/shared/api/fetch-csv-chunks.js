import { fetchText } from "./fetch-resource.js";

function chunkManifestPath(csvPath) {
  return `${csvPath}.chunks/index.json`;
}

export async function loadInitialCsvChunk(csvPath, signal) {
  let manifestText;
  try {
    manifestText = await fetchText(chunkManifestPath(csvPath), signal);
  } catch (error) {
    if (error.status === 404) {
      return { csvText: await fetchText(csvPath, signal), chunks: null, nextChunkIndex: null };
    }
    throw error;
  }

  let manifest;
  try {
    manifest = JSON.parse(manifestText);
  } catch {
    // Static hosts with SPA rewrites may return index.html for a missing legacy chunk index.
    if (/^\s*</.test(manifestText) || /^\uFEFF?time,/i.test(manifestText)) {
      return { csvText: await fetchText(csvPath, signal), chunks: null, nextChunkIndex: null };
    }
    throw new Error(`${chunkManifestPath(csvPath)} is not valid JSON.`);
  }
  if (!Array.isArray(manifest?.chunks) || manifest.chunks.some((chunk) => (
    typeof chunk !== "string" || !/^chunk-\d{6,}\.csv$/.test(chunk)
  ))) {
    throw new Error(`${chunkManifestPath(csvPath)} must contain a chunks array.`);
  }
  if (manifest.chunks.length === 0) {
    return { csvText: await fetchText(csvPath, signal), chunks: null, nextChunkIndex: null };
  }

  const csvText = await fetchText(`${csvPath}.chunks/${manifest.chunks[0]}`, signal);
  return { csvText, chunks: manifest.chunks, nextChunkIndex: 1 };
}

export async function loadOlderCsvChunk(csvPath, chunks, index, signal) {
  if (!Array.isArray(chunks) || index < 0 || index >= chunks.length) return null;
  return fetchText(`${csvPath}.chunks/${chunks[index]}`, signal);
}
