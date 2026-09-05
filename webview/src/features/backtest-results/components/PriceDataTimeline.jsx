import { ArrowRight, CalendarRange } from "lucide-react";

import { useResourceJson } from "../../../shared/hooks/use-resource-json.js";
import { extractPriceDataRange, formatUtcDate } from "../../../shared/lib/price-data-range.js";

function durationLabel(elapsedDays) {
  if (elapsedDays === 0) return "Same day";
  return `${elapsedDays.toLocaleString()} day${elapsedDays === 1 ? "" : "s"}`;
}

export function PriceDataTimeline({ dfPath }) {
  const { data: range, loading } = useResourceJson(dfPath, extractPriceDataRange, { allowMissing: true });
  const available = range && Number.isFinite(range.start) && Number.isFinite(range.end);

  return (
    <div className="min-w-0 space-y-1" aria-live="polite">
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <CalendarRange aria-hidden="true" className="size-4" />
        Price data coverage
      </p>
      {available ? (
        <>
          <h2 className="flex flex-wrap items-center gap-2 font-heading text-xl font-semibold tracking-tight sm:text-2xl">
            <span className="sr-only">Start date: </span>
            <span className="tabular-nums" data-testid="price-range-start">{formatUtcDate(range.start)}</span>
            <ArrowRight aria-hidden="true" className="size-5 shrink-0 text-muted-foreground" />
            <span className="sr-only">End date: </span>
            <span className="tabular-nums" data-testid="price-range-end">{formatUtcDate(range.end)}</span>
          </h2>
          <p className="text-xs text-muted-foreground" data-testid="price-range-duration">
            {durationLabel(range.elapsedDays)} of price data · UTC
          </p>
        </>
      ) : (
        <h2 className="font-heading text-xl font-semibold tracking-tight text-muted-foreground sm:text-2xl">
          {loading ? "Reading price data…" : "Price data range is unavailable."}
        </h2>
      )}
    </div>
  );
}
