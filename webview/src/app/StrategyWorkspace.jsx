import { useEffect, useState } from "react";

import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AppHeader } from "./AppShell.jsx";
import { BacktestResultsPage } from "../features/backtest-results/BacktestResultsPage.jsx";
import { MarketChartPage } from "../features/market-chart/MarketChartPage.jsx";
import { parseStrategyConfig } from "../features/strategies/lib/strategy-config.js";
import { Alert } from "../shared/components/Alert.jsx";
import { useResourceJson } from "../shared/hooks/use-resource-json.js";

const VALID_TABS = new Set(["chart", "results"]);

function tabFromHash() {
  const hash = window.location.hash.slice(1);
  return VALID_TABS.has(hash) ? hash : "chart";
}

export function StrategyWorkspace({ strategy }) {
  const [activeTab, setActiveTab] = useState(tabFromHash);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const { data: config, error: configError, loading: configLoading } = useResourceJson(
    strategy.resources.config,
    parseStrategyConfig,
  );
  const symbolPaths = config
    ? new Map(config.symbols.map((symbol) => [
      symbol,
      strategy.resources.df.find((resource) => resource.name === symbol)?.path,
    ]))
    : new Map();
  const resourceError = config && [...symbolPaths.values()].some((path) => !path)
    ? "Strategy config symbols must each have a matching CSV resource in the manifest."
    : "";
  const dfPath = symbolPaths.get(selectedSymbol) ?? "";

  useEffect(() => {
    const handleLocationChange = () => setActiveTab(tabFromHash());
    window.addEventListener("hashchange", handleLocationChange);
    window.addEventListener("popstate", handleLocationChange);
    return () => {
      window.removeEventListener("hashchange", handleLocationChange);
      window.removeEventListener("popstate", handleLocationChange);
    };
  }, []);

  useEffect(() => {
    if (!config?.symbols.length) return;
    if (!config.symbols.includes(selectedSymbol)) setSelectedSymbol(config.symbols[0]);
  }, [config, selectedSymbol]);

  function selectTab(tab) {
    setActiveTab(tab);
    if (window.location.hash !== `#${tab}`) window.history.pushState(null, "", `#${tab}`);
  }

  return (
    <Tabs value={activeTab} onValueChange={selectTab} className="h-full gap-0 overflow-hidden bg-background">
      <AppHeader
        center={
          <div className="flex justify-center">
            <TabsList
              aria-label="Backtest views"
              activateOnFocus
              className="h-12! rounded-2xl border border-foreground/25 bg-muted p-0.5 shadow-md"
            >
              <TabsTrigger
                value="chart"
                className="rounded-xl px-5 py-2.5 text-base font-semibold text-foreground/75 data-active:bg-background data-active:text-foreground data-active:shadow-md data-active:ring-1 data-active:ring-foreground/15 dark:data-active:bg-background"
              >
                Chart
              </TabsTrigger>
              <TabsTrigger
                value="results"
                className="rounded-xl px-5 py-2.5 text-base font-semibold text-foreground/75 data-active:bg-background data-active:text-foreground data-active:shadow-md data-active:ring-1 data-active:ring-foreground/15 dark:data-active:bg-background"
              >
                Backtest Results
              </TabsTrigger>
            </TabsList>
          </div>
        }
        end={
          <div className="flex items-center justify-center gap-2 sm:justify-end">
            <Label htmlFor="workspace-symbol-select" className="text-base text-muted-foreground">Symbol</Label>
            <Select
              items={(config?.symbols ?? []).map((symbol) => ({ label: symbol, value: symbol }))}
              value={selectedSymbol || null}
              onValueChange={setSelectedSymbol}
              disabled={configLoading || Boolean(configError || resourceError)}
            >
              <SelectTrigger id="workspace-symbol-select" aria-label="Symbol" className="min-w-28 h-[45px]!">
                <SelectValue placeholder="Select symbol" />
              </SelectTrigger>
              <SelectContent>
                {(config?.symbols ?? []).map((symbol) => <SelectItem key={symbol} value={symbol}>{symbol}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        }
      />
      <main className="relative min-h-0 flex-1">
        {(configLoading || configError || resourceError || !selectedSymbol) ? (
          <div className="mx-auto w-full max-w-[100rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            {!selectedSymbol && <Alert role="status">Selecting the default symbol…</Alert>}
            {configLoading && <Alert role="status">Loading strategy configuration…</Alert>}
            {(configError || resourceError) && <Alert kind="error" role="alert">Strategy configuration could not be used: {configError || resourceError}</Alert>}
          </div>
        ) : (
          <>
        <TabsContent value="chart" keepMounted className="absolute inset-0 m-0 overflow-hidden data-hidden:hidden">
          <MarketChartPage key={selectedSymbol} active={activeTab === "chart"} config={config} symbol={selectedSymbol} dfPath={dfPath} resultPath={strategy.resources.result} />
        </TabsContent>
        <TabsContent value="results" keepMounted className="absolute inset-0 m-0 overflow-x-hidden overflow-y-auto data-hidden:hidden">
          <BacktestResultsPage active={activeTab === "results"} symbol={selectedSymbol} resultPath={strategy.resources.result} dfPath={dfPath} />
        </TabsContent>
          </>
        )}
      </main>
    </Tabs>
  );
}
