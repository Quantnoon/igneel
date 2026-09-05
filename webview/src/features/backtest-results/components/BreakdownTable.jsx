import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { displayValue, humanize } from "../../../shared/lib/formatters.js";
import { breakdownRows } from "../lib/backtest-results-data.js";

export function BreakdownTable({ title, breakdown, order = [], emptyMessage, skip = false }) {
  const rows = breakdownRows(breakdown, order);
  const headers = skip ? ["Reason", "Count"] : ["Category", "Trades", "Wins", "Losses", "P&L (USD)"];

  return (
    <Card className="min-w-0 self-start" size="sm">
      <CardHeader className="border-b"><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        {!rows.length ? <p className="text-sm text-muted-foreground">{emptyMessage}</p> : (
          <div className="overflow-hidden rounded-lg ring-1 ring-foreground/10 [&_[data-slot=table-container]]:max-h-[28rem] [&_[data-slot=table-container]]:overflow-auto">
            <Table className="text-xs">
              <TableHeader className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm"><TableRow>{headers.map((label, index) => <TableHead className={index ? "h-9 text-right" : "h-9"} key={label}>{label}</TableHead>)}</TableRow></TableHeader>
              <TableBody>
                {rows.map(([name, values]) => (
                  <TableRow key={name}>
                    <TableCell className="font-medium">{humanize(name)}</TableCell>
                    {skip ? <TableCell className="text-right tabular-nums">{displayValue(values)}</TableCell> : <>
                      <TableCell className="text-right tabular-nums">{displayValue(values?.trades)}</TableCell>
                      <TableCell className="text-right tabular-nums text-emerald-400">{displayValue(values?.wins)}</TableCell>
                      <TableCell className="text-right tabular-nums text-red-400">{displayValue(values?.losses)}</TableCell>
                      <TableCell className="text-right font-medium tabular-nums">{displayValue(values?.pnl_dollar)}</TableCell>
                    </>}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
