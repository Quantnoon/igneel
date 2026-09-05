import { useEffect, useState } from "react";

import { fetchText } from "../../shared/api/fetch-resource.js";
import { MANIFEST_PATH, parseStrategyManifest } from "./lib/manifest.js";

export function useStrategies(env) {
  const [state, setState] = useState({ strategies: null, error: null, loading: true });

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();
    setState({ strategies: null, error: null, loading: true });

    fetchText(MANIFEST_PATH, controller.signal).then(
      (text) => {
        if (!mounted) return;
        try {
          setState({ strategies: parseStrategyManifest(text, env), error: null, loading: false });
        } catch (error) {
          setState({ strategies: null, error: error.message ?? String(error), loading: false });
        }
      },
      (error) => {
        if (!mounted || error.name === "AbortError") return;
        setState({ strategies: null, error: error.message ?? String(error), loading: false });
      },
    );

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [env]);

  return state;
}
