import { LoaderCircle } from "lucide-react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function MarketChartSymbolSelect({
  symbol,
  symbols,
  pendingSymbol,
  visible = true,
  open,
  onOpenChange,
  onValueChange,
}) {
  const controlledOpenProps = open === undefined ? {} : {
    open: visible && open,
    onOpenChange,
  };

  return (
    <Select value={symbol} onValueChange={onValueChange} {...controlledOpenProps}>
      <SelectTrigger aria-label="Chart symbol" className="h-10! min-w-36 border-foreground/15 bg-[#111111] text-sm text-foreground hover:bg-[#171717]">
        <SelectValue placeholder="Select symbol" />
      </SelectTrigger>
      <SelectContent className="border-foreground/15 bg-[#111111] text-foreground">
        {symbols.map((option) => (
          <SelectItem key={option} value={option}>
            <span className="flex flex-1 items-center justify-between gap-2">
              <span>{option}</span>
              {pendingSymbol === option && (
                <LoaderCircle
                  aria-hidden="true"
                  className="size-4 shrink-0 animate-spin"
                  data-testid="symbol-activation-spinner"
                />
              )}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
