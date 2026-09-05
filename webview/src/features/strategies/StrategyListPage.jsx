import { ArrowRight } from "lucide-react";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Link } from "../../app/router.jsx";
import { Alert } from "../../shared/components/Alert.jsx";
import { isAccessible } from "./lib/manifest.js";

export function StrategyListPage({ strategies, error, loading, env }) {
  const accessible = strategies?.filter(isAccessible) ?? [];

  return (
    <div className="mx-auto w-full max-w-[100rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="grid gap-1">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">Strategies</h2>
        <p className="text-sm text-muted-foreground">Choose a strategy to open its chart and backtest results.</p>
      </div>

      <div className="mt-6 grid gap-3">
        {loading && <Alert role="status">Loading strategies…</Alert>}
        {error && <Alert kind="error" role="alert">Strategy manifest could not be loaded: {error}</Alert>}
        {!loading && !error && accessible.length === 0 && (
          <Alert>
            No strategies are ready yet. Run a backtest to generate its files, or fill in the {env} resource
            URLs in strategies.json to make a strategy accessible.
          </Alert>
        )}
      </div>

      {!loading && !error && accessible.length > 0 && (
        <ul className="mt-2 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {accessible.map((strategy) => (
            <li key={strategy.name}>
              <Link
                to={`/${strategy.name}`}
                className="block rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <Card size="sm" className="h-full transition-colors hover:bg-muted/40">
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between gap-2">
                      {strategy.name}
                      <ArrowRight aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                    </CardTitle>
                    <CardDescription>Chart and backtest results</CardDescription>
                  </CardHeader>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
