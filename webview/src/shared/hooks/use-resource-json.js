import { useEffect, useRef, useState } from "react";

import { fetchText } from "../api/fetch-resource.js";

export function useResourceJson(path, parse, { allowMissing = false } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const parserRef = useRef(parse);
  parserRef.current = parse;

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function load() {
      try {
        const text = await fetchText(path, controller.signal);
        if (!active) return;
        const data = parserRef.current(text);
        setState({ data, error: null, loading: false });
      } catch (error) {
        if (!active || error.name === "AbortError") return;
        if (allowMissing && error.status === 404) {
          setState({ data: [], error: null, loading: false });
          return;
        }
        setState({ data: null, error: error.message ?? String(error), loading: false });
      }
    }

    load();
    return () => {
      active = false;
      controller.abort();
    };
  }, [allowMissing, path]);

  return state;
}
