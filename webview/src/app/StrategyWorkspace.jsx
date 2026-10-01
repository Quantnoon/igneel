import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { Tabs, TabsContent } from "@/components/ui/tabs";
import { AppHeader } from "./AppShell.jsx";
import { BacktestResultsPage } from "../features/backtest-results/BacktestResultsPage.jsx";
import { MarketChartPage } from "../features/market-chart/MarketChartPage.jsx";
import { parseStrategyConfig } from "../features/strategies/lib/strategy-config.js";
import { Alert } from "../shared/components/Alert.jsx";
import { useResourceJson } from "../shared/hooks/use-resource-json.js";

const VALID_TABS = new Set(["chart", "results"]);

function tabFromHash(hashValue) {
  const hash = hashValue.slice(1);
  return VALID_TABS.has(hash) ? hash : "chart";
}

export function StrategyWorkspace({ strategy }) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = tabFromHash(location.hash);
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
    if (!config?.symbols.length) return;
    if (!config.symbols.includes(selectedSymbol)) setSelectedSymbol(config.symbols[0]);
  }, [config, selectedSymbol]);

  function selectTab(tab) {
    if (location.hash !== `#${tab}`) {
      navigate({ pathname: location.pathname, search: location.search, hash: `#${tab}` });
    }
  }

  return (
    <Tabs value={activeTab} onValueChange={selectTab} className="h-full gap-0 overflow-hidden bg-background">
      <AppHeader showBack botUrls={strategy.botUrls} />
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
          <MarketChartPage key={selectedSymbol} active={activeTab === "chart"} config={config} symbol={selectedSymbol} symbols={config.symbols} onSymbolChange={setSelectedSymbol} onViewBacktestResults={() => selectTab("results")} dfPath={dfPath} resultPath={strategy.resources.result} />
        </TabsContent>
        <TabsContent value="results" keepMounted className="absolute inset-0 m-0 overflow-x-hidden overflow-y-auto data-hidden:hidden">
          <BacktestResultsPage active={activeTab === "results"} symbol={selectedSymbol} symbols={config.symbols} onSymbolChange={setSelectedSymbol} resultPath={strategy.resources.result} dfPath={dfPath} onBackToChart={() => selectTab("chart")} />
        </TabsContent>
          </>
        )}
      </main>
    </Tabs>
  );
}
