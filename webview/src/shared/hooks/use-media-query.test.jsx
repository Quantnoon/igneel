import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { useMediaQuery } from "./use-media-query.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("returns the current match state for the query", () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })));

  const { result } = renderHook(() => useMediaQuery("(max-width: 767px)"));

  expect(result.current).toBe(true);
});

test("updates when the media query match state changes", () => {
  let changeListener;
  const removeEventListener = vi.fn();
  vi.stubGlobal("matchMedia", vi.fn(() => ({
    matches: false,
    addEventListener: (type, handler) => { changeListener = handler; },
    removeEventListener,
  })));

  const { result, unmount } = renderHook(() => useMediaQuery("(max-width: 767px)"));
  expect(result.current).toBe(false);

  act(() => changeListener({ matches: true }));
  expect(result.current).toBe(true);

  unmount();
  expect(removeEventListener).toHaveBeenCalledWith("change", changeListener);
});

test("falls back to false when matchMedia is unavailable", () => {
  vi.stubGlobal("matchMedia", undefined);

  const { result } = renderHook(() => useMediaQuery("(max-width: 767px)"));

  expect(result.current).toBe(false);
});
