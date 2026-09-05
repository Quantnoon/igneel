import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Item, ItemActions, ItemContent, ItemGroup, ItemTitle } from "@/components/ui/item";
import { displayValue } from "../../../shared/lib/formatters.js";
import { parseFormattedNumber } from "../lib/backtest-results-data.js";

const GROUPS = [
  ["Account", [["currency", "Currency"], ["starting_balance", "Starting balance"], ["final_balance", "Final balance"], ["peak_balance", "Peak balance"], ["total_return_pct", "Total return"], ["max_drawdown_pct", "Max drawdown"]]],
  ["Trades", [["trades_taken", "Trades taken"], ["trades_skipped", "Trades skipped"], ["win_rate_pct", "Win rate"]]],
  ["Risk", [["profit_factor", "Profit factor"], ["sharpe_ratio", "Sharpe ratio"], ["sortino_ratio", "Sortino ratio"]]],
  ["Profit and loss", [["avg_win", "Average win"], ["avg_loss", "Average loss"], ["gross_profit", "Gross profit"], ["gross_loss", "Gross loss"]]],
];

function comparisonTone(value, baseline = 0) {
  if (value === null || !Number.isFinite(value) || value === baseline) return "";
  return value > baseline ? "text-emerald-400" : "text-red-400";
}

export function metricValueTone(field, report) {
  const value = parseFormattedNumber(report[field]);
  const startingBalance = parseFormattedNumber(report.starting_balance);

  switch (field) {
    case "final_balance":
    case "peak_balance":
      return startingBalance === null ? "" : comparisonTone(value, startingBalance);
    case "total_return_pct":
    case "avg_win":
    case "gross_profit":
      return comparisonTone(value);
    case "max_drawdown_pct":
      return value !== null && Number.isFinite(value) && value > 0 ? "text-red-400" : "";
    case "win_rate_pct":
      return comparisonTone(value, 50);
    case "profit_factor":
      return comparisonTone(value, 1);
    case "avg_loss":
    case "gross_loss":
      return value !== null && Number.isFinite(value) && value !== 0 ? "text-red-400" : "";
    default:
      return "";
  }
}

export function MetricsGrid({ report }) {
  return (
    <div className="grid items-start grid-cols-[repeat(auto-fit,minmax(15rem,1fr))] gap-4">
      {GROUPS.map(([groupName, metrics]) => (
        <Card className="min-w-0 self-start" size="sm" key={groupName}>
          <CardHeader className="border-b"><CardTitle>{groupName}</CardTitle></CardHeader>
          <CardContent>
            <ItemGroup>
              {metrics.map(([field, label]) => (
                <Item size="xs" key={field}>
                  <ItemContent className="min-w-0"><ItemTitle>{label}</ItemTitle></ItemContent>
                  <ItemActions className="min-w-0"><strong data-metric={field} className={`break-all text-right tabular-nums ${metricValueTone(field, report)}`}>{displayValue(report[field])}</strong></ItemActions>
                </Item>
              ))}
            </ItemGroup>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
