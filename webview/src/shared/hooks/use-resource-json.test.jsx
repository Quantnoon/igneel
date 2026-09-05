import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { useResourceJson } from "./use-resource-json.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("fetches the resource once and parses the payload", async () => {
  const payload = [{ symbol: "Volatility 25 Index" }];
  const fetchSpy = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }));

  vi.stubGlobal("fetch", fetchSpy);

  const { result } = renderHook(() => useResourceJson("result.json", JSON.parse));

  await waitFor(() => expect(result.current.data).toEqual(payload));
  expect(result.current.error).toBeNull();
  expect(result.current.loading).toBe(false);
  expect(fetchSpy).toHaveBeenCalledTimes(1);
});

test("maps a 404 to empty data when allowMissing is set", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("not found", { status: 404 })));

  const { result } = renderHook(() =>
    useResourceJson("result.json", JSON.parse, { allowMissing: true }),
  );

  await waitFor(() => expect(result.current.data).toEqual([]));
  expect(result.current.error).toBeNull();
  expect(result.current.loading).toBe(false);
});

test("surfaces the error message when the request fails", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500 })));

  const { result } = renderHook(() => useResourceJson("result.json", JSON.parse));

  await waitFor(() => expect(result.current.error).toMatch(/500/));
  expect(result.current.data).toBeNull();
  expect(result.current.loading).toBe(false);
});
