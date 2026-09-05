import { useMemo } from "react";
import { Alert } from "../../shared/components/Alert.jsx";
import { useResourceJson } from "../../shared/hooks/use-resource-json.js";
import { formatMoney } from "../../shared/lib/formatters.js";
import { BREAKDOWN_CONFIG, buildBalanceChart, buildBreakdownChart, buildDrawdownChart, buildSkipChart } from "./chart-options.js";
import { BreakdownTable } from "./components/BreakdownTable.jsx";
import { MetricsGrid } from "./components/MetricsGrid.jsx";
import { PriceDataTimeline } from "./components/PriceDataTimeline.jsx";
import { ResultChart } from "./components/ResultChart.jsx";
import { TradeLogTable } from "./components/TradeLogTable.jsx";
import { DAY_ORDER, SESSION_ORDER, flattenResults } from "./lib/backtest-results-data.js";

function parseResults(text) {
  return flattenResults(JSON.parse(text));
}

export function BacktestResultsPage({ active, resultPath, dfPath, symbol }) {
  const { data: results, error, loading } = useResourceJson(resultPath, parseResults, { allowMissing: true });
  const availableResults = results ?? [];
  const selected = useMemo(() => availableResults.find((result) => result.symbol === symbol) ?? null, [availableResults, symbol]);

  const balanceChart = useMemo(
    () => selected ? buildBalanceChart(selected.report, selected.trades) : null,
    [selected],
  );
  const drawdownOptions = useMemo(
    () => balanceChart ? buildDrawdownChart(balanceChart.balance) : null,
    [balanceChart],
  );
  const dayOptions = useMemo(
    () => selected ? buildBreakdownChart(BREAKDOWN_CONFIG.day.title, selected.report.day_breakdown, DAY_ORDER) : null,
    [selected],
  );
  const sessionOptions = useMemo(
    () => selected ? buildBreakdownChart(BREAKDOWN_CONFIG.session.title, selected.report.session_breakdown, SESSION_ORDER) : null,
    [selected],
  );
  const skipOptions = useMemo(
    () => selected ? buildSkipChart(selected.report.skip_breakdown) : null,
    [selected],
  );

  return (
    <div className="mx-auto w-full max-w-[100rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="flex flex-col items-stretch justify-between gap-5 md:flex-row md:items-end">
        <PriceDataTimeline dfPath={dfPath} />
        <p className="font-mono text-sm text-muted-foreground">{symbol}</p>
      </div>

      <div className="mt-5 grid gap-3">
        {loading && <Alert>Loading backtest results…</Alert>}
        {error && <Alert kind="error" role="alert">Backtest results could not be loaded: {error}</Alert>}
        {!loading && !error && !selected && <Alert>No backtest results are available for {symbol}. Run a backtest to populate this strategy.</Alert>}
      </div>

      {selected && balanceChart && (
        <div className="mt-7 grid gap-6 lg:gap-8">
          <div>
            <p className="text-sm text-muted-foreground">Selected backtest</p>
            <h2 className="break-words font-heading text-xl font-semibold tracking-tight">{selected.symbol} · {selected.name}</h2>
          </div>

          <section aria-label="Account performance">
            <ResultChart options={balanceChart.options} description="Account balance after every trade, including flat points for skipped trades." active={active} wide>
              {!balanceChart.balance.reconciles && (
                <Alert role="status">
                  Trade log ends at {formatMoney(balanceChart.balance.actualFinalBalance, balanceChart.balance.currency)}, but the report final balance is {formatMoney(balanceChart.balance.expectedFinalBalance, balanceChart.balance.currency)}.
                </Alert>
              )}
            </ResultChart>
          </section>

          <section className="grid gap-3" aria-labelledby="summary-heading">
            <div>
              <h3 id="summary-heading" className="font-heading text-lg font-semibold tracking-tight">Performance summary</h3>
              <p className="text-sm text-muted-foreground">Account, trade, risk, and profitability metrics.</p>
            </div>
            <MetricsGrid report={selected.report} />
          </section>

          <section className="grid gap-4" aria-label="Performance charts">
            <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
              <ResultChart options={drawdownOptions} description="Percentage decline from the running account balance peak." active={active} wide />
              <ResultChart options={dayOptions} description="Performance by day showing wins, losses, and profit or loss." active={active} />
              <ResultChart options={sessionOptions} description="Performance by session showing wins, losses, and profit or loss." active={active} />
              {skipOptions && <ResultChart options={skipOptions} description="Number of skipped trades grouped by reason." active={active} wide />}
            </div>
          </section>

          <section className="grid gap-3" aria-labelledby="breakdowns-heading">
            <div>
              <h3 id="breakdowns-heading" className="font-heading text-lg font-semibold tracking-tight">Detailed breakdowns</h3>
              <p className="text-sm text-muted-foreground">Performance totals grouped by day, session, and skip reason.</p>
            </div>
            <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-3">
              <BreakdownTable title="Day Breakdown" breakdown={selected.report.day_breakdown} order={DAY_ORDER} emptyMessage="No day breakdown is available." />
              <BreakdownTable title="Session Breakdown" breakdown={selected.report.session_breakdown} order={SESSION_ORDER} emptyMessage="No session breakdown is available." />
              <BreakdownTable title="Skip Breakdown" breakdown={selected.report.skip_breakdown} emptyMessage="No skipped trades." skip />
            </div>
          </section>

          <TradeLogTable key={selected.key} trades={selected.trades} />
        </div>
      )}
    </div>
  );
}
