import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { displayValue, formatTimestamp, humanize } from "../../../shared/lib/formatters.js";
import { filterAndSortTrades, orderedTradeColumns } from "../lib/backtest-results-data.js";

const PAGE_SIZE = 25;
const RIGHT_ALIGNED_COLUMNS = new Set([
  "entry", "exit", "sl", "tp", "pnl", "pnl_dollar", "pnl_currency",
  "balance_before", "balance_after",
]);

function valueTone(column, value) {
  const normalized = String(value ?? "").toLowerCase();
  if (column === "result") {
    if (normalized.includes("win") || normalized.includes("profit")) return "bg-emerald-500/10 text-emerald-400";
    if (normalized.includes("loss")) return "bg-red-500/10 text-red-400";
    if (normalized.includes("skip")) return "bg-amber-500/10 text-amber-400";
  }
  if (column === "position") {
    if (normalized === "buy" || normalized === "long") return "bg-blue-500/10 text-blue-400";
    if (normalized === "sell" || normalized === "short") return "bg-violet-500/10 text-violet-400";
  }
  if (column === "skipped" && (value === true || normalized === "true")) return "bg-amber-500/10 text-amber-400";
  return "";
}

function displayTradeValue(trade, column) {
  const value = column.endsWith("_time") ? formatTimestamp(trade[column]) : displayValue(trade[column]);
  const tone = valueTone(column, trade[column]);
  return tone
    ? <span className={`inline-flex rounded-md px-2 py-0.5 font-medium ${tone}`}>{value}</span>
    : value;
}

export function TradeLogTable({ trades }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState({ column: undefined, direction: "asc" });
  const [page, setPage] = useState(1);
  const columns = useMemo(() => orderedTradeColumns(trades), [trades]);
  const filtered = useMemo(
    () => filterAndSortTrades(trades, columns, query, sort.column, sort.direction),
    [columns, query, sort, trades],
  );
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageRows = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const isNumericColumn = (column) => RIGHT_ALIGNED_COLUMNS.has(column)
    || trades.some((trade) => typeof trade[column] === "number");

  function changeSort(column) {
    setSort((current) => current.column === column
      ? { column, direction: current.direction === "asc" ? "desc" : "asc" }
      : { column, direction: "asc" });
    setPage(1);
  }

  return (
    <Card className="min-w-0" size="sm">
      <CardHeader className="gap-4 border-b md:grid-cols-[1fr_auto]">
        <div>
          <p className="text-sm text-muted-foreground">Complete data</p>
          <CardTitle>Trade Log</CardTitle>
        </div>
        <div className="grid gap-2 md:w-80">
          <Label htmlFor="trade-search">Search trades</Label>
          <Input
            id="trade-search"
            type="search"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setPage(1); }}
            placeholder="Search any column…"
          />
        </div>
      </CardHeader>
      <CardContent>
        {!columns.length ? <p className="text-sm text-muted-foreground">No trades were returned for this strategy.</p> : (
          <div className="overflow-hidden rounded-lg ring-1 ring-foreground/10 [&_[data-slot=table-container]]:max-h-[36rem] [&_[data-slot=table-container]]:overflow-auto">
            <Table className="text-xs">
              <TableHeader className="bg-muted/80 backdrop-blur-sm">
                <TableRow>{columns.map((column) => {
                  const rightAligned = isNumericColumn(column);
                  const sorted = sort.column === column;
                  return (
                    <TableHead
                      className={`sticky top-0 z-10 h-9 bg-muted ${rightAligned ? "text-right" : ""}`}
                      key={column}
                      aria-sort={sorted ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}
                    >
                      <Button className={rightAligned ? "ml-auto" : "-ml-2"} variant="ghost" size="xs" type="button" onClick={() => changeSort(column)}>
                        {humanize(column)}
                        {sorted && (sort.direction === "asc" ? <ArrowUp data-icon="inline-end" /> : <ArrowDown data-icon="inline-end" />)}
                      </Button>
                    </TableHead>
                  );
                })}</TableRow>
              </TableHeader>
              <TableBody>
                {pageRows.map((trade, rowIndex) => (
                  <TableRow key={`${trade.open_time ?? "trade"}-${rowIndex}`} data-result={trade.result ?? ""}>
                    {columns.map((column) => (
                      <TableCell className={isNumericColumn(column) ? "text-right tabular-nums" : ""} key={column}>
                        {displayTradeValue(trade, column)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
                {!pageRows.length && (
                  <TableRow><TableCell className="h-24 text-center text-muted-foreground" colSpan={columns.length}>No trades match your search.</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
      {columns.length > 0 && (
        <CardFooter className="flex flex-col items-stretch justify-between gap-3 text-xs text-muted-foreground sm:flex-row sm:items-center">
          <span>{filtered.length.toLocaleString()} trade{filtered.length === 1 ? "" : "s"} · Page {currentPage} of {pageCount}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" type="button" disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
              <ChevronLeft data-icon="inline-start" />Previous
            </Button>
            <Button variant="outline" size="sm" type="button" disabled={currentPage >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>
              Next<ChevronRight data-icon="inline-end" />
            </Button>
          </div>
        </CardFooter>
      )}
    </Card>
  );
}
