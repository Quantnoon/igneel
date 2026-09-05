import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

const strategiesDirectory = fileURLToPath(new URL("./strategies", import.meta.url));

// Emits generated strategy resources beside dist/index.html so the built webview can fetch
// them at runtime. Hosting must rewrite /[name] requests to index.html
// so direct links to a strategy resolve to the SPA.
function strategyResources() {
  function emitDirectory(context, directory, outputPrefix = "strategies") {
    for (const entry of readdirSync(directory)) {
      const path = join(directory, entry);
      const outputPath = `${outputPrefix}/${entry}`;
      if (statSync(path).isDirectory()) emitDirectory(context, path, outputPath);
      else context.emitFile({ type: "asset", fileName: outputPath, source: readFileSync(path) });
    }
  }

  return {
    name: "emit-strategy-resources",
    apply: "build",
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
