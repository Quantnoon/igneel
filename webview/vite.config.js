import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, relative, resolve, sep } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import { chunkCsvText } from "./src/shared/lib/csv-records.js";

const strategiesDirectory = fileURLToPath(new URL("./strategies", import.meta.url));
const CSV_CHUNK_SIZE = 1000;

function chunkAssets(csvText) {
  const chronologicalChunks = chunkCsvText(csvText, CSV_CHUNK_SIZE);
  const entries = chronologicalChunks.map((source, index) => ({
    name: `chunk-${String(index).padStart(6, "0")}.csv`,
    source,
  }));
  return {
    entries,
    manifest: JSON.stringify({ chunks: entries.map(({ name }) => name).reverse() }),
  };
}

// Emits generated strategy resources beside dist/index.html so the built webview can fetch
// them at runtime. Hosting must rewrite /[name] requests to index.html
// so direct links to a strategy resolve to the SPA.
function strategyResources() {
  function emitDirectory(context, directory, outputPrefix = "strategies") {
    for (const entry of readdirSync(directory)) {
      const path = join(directory, entry);
      const outputPath = `${outputPrefix}/${entry}`;
      if (statSync(path).isDirectory()) emitDirectory(context, path, outputPath);
      else {
        const source = readFileSync(path);
        context.emitFile({ type: "asset", fileName: outputPath, source });
        if (extname(path).toLowerCase() !== ".csv") continue;
        const { entries, manifest } = chunkAssets(source.toString("utf8"));
        for (const chunk of entries) {
          context.emitFile({
            type: "asset",
            fileName: `${outputPath}.chunks/${chunk.name}`,
            source: chunk.source,
          });
        }
        context.emitFile({
          type: "asset",
          fileName: `${outputPath}.chunks/index.json`,
          source: manifest,
        });
      }
    }
  }

  function devChunkMiddleware(req, res, next) {
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
    } catch {
      res.statusCode = 400;
      res.end("Invalid strategy resource URL.");
      return;
    }
    const marker = ".csv.chunks/";
    const markerIndex = pathname.indexOf(marker);
    if (!pathname.startsWith("/strategies/") || markerIndex < 0) return next();

    const csvResource = pathname.slice(1, markerIndex + 4);
    const chunkName = pathname.slice(markerIndex + marker.length);
    const diskPath = resolve(strategiesDirectory, csvResource.slice("strategies/".length));
    const diskRelative = relative(strategiesDirectory, diskPath);
    if (diskRelative.startsWith(`..${sep}`) || diskRelative === "..") {
      res.statusCode = 400;
      res.end("Invalid strategy resource path.");
      return;
    }

    try {
      const csvText = readFileSync(diskPath, "utf8");
      const { entries, manifest } = chunkAssets(csvText);
      if (chunkName === "index.json") {
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end(manifest);
        return;
      }
      const chunk = entries.find(({ name }) => name === chunkName);
      if (!chunk) {
        res.statusCode = 404;
        res.end("CSV chunk not found.");
        return;
      }
      res.setHeader("Content-Type", "text/csv; charset=utf-8");
      res.end(chunk.source);
    } catch (error) {
      if (error.code === "ENOENT") {
        res.statusCode = 404;
        res.end("CSV resource not found.");
        return;
      }
      next(error);
    }
  }

  return {
    name: "emit-strategy-resources",
    configureServer(server) {
      server.middlewares.use(devChunkMiddleware);
    },
    generateBundle() {
      emitDirectory(this, strategiesDirectory);
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), strategyResources()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.{test,spec}.{js,jsx}"],
    pool: "threads",
    maxWorkers: 1,
    restoreMocks: true,
  },
});
