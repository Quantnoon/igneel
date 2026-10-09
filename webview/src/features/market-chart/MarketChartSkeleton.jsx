import { Skeleton } from "@/components/ui/skeleton";
import { MarketChartSymbolSelect } from "./MarketChartSymbolSelect.jsx";

function ToolbarSkeleton({ symbol, symbols, pendingSymbol, symbolMenuOpen, onSymbolMenuOpenChange, onSymbolChange }) {
  return (
    <div className="flex min-h-14 flex-wrap items-center gap-3 border-b border-foreground/10 px-4 py-2">
      <div className="flex gap-1.5">
        <Skeleton aria-hidden="true" className="h-10 w-12" />
        <Skeleton aria-hidden="true" className="h-10 w-12" />
        <Skeleton aria-hidden="true" className="h-10 w-12" />
      </div>
      {symbols?.length ? (
        <MarketChartSymbolSelect
          symbol={symbol}
          symbols={symbols}
          pendingSymbol={pendingSymbol}
          open={symbolMenuOpen}
          onOpenChange={onSymbolMenuOpenChange}
          onValueChange={onSymbolChange}
        />
      ) : <Skeleton aria-hidden="true" className="h-10 w-36" />}
      <Skeleton aria-hidden="true" className="ml-auto h-9 w-36" />
    </div>
  );
}

export function MarketChartSkeleton(props = {}) {
  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-[#0a0a0a]" role="status" aria-label="Loading chart" data-testid="market-chart-skeleton">
      <ToolbarSkeleton {...props} />
      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col" aria-hidden="true">
          <div className="flex min-h-0 flex-1 items-stretch gap-3 p-5">
            <div className="flex min-h-0 flex-1 flex-col justify-between py-2">
              <Skeleton className="h-px w-full" />
              <Skeleton className="h-px w-full" />
              <Skeleton className="h-px w-full" />
              <Skeleton className="h-px w-full" />
              <Skeleton className="h-px w-full" />
            </div>
            <Skeleton className="my-2 h-4/5 w-8 shrink-0 self-end" />
          </div>
        </section>
        <aside className="hidden w-64 shrink-0 flex-col gap-4 overflow-hidden border-l border-foreground/10 bg-[#0d0d0d] p-4 md:flex" aria-hidden="true">
          <Skeleton className="mb-1 h-5 w-24" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-4/5" />
          <Skeleton className="h-8 w-3/4" />
        </aside>
      </div>
    </div>
  );
}
