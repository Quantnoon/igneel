import { Route, Routes, useLocation, useParams } from "react-router";

import { AppShell } from "./AppShell.jsx";
import { StrategyWorkspace } from "./StrategyWorkspace.jsx";
import { StrategyListPage } from "../features/strategies/StrategyListPage.jsx";
import { StrategyConfigErrorPage, StrategyNotFoundPage } from "../features/strategies/StrategyStatusPages.jsx";
import { useStrategies } from "../features/strategies/use-strategies.js";
import { activeEnvironment, findStrategy } from "../features/strategies/lib/manifest.js";
import { Alert } from "../shared/components/Alert.jsx";

function StrategyRoute({ strategies, error, loading, env }) {
  const { strategyName } = useParams();
  const strategy = strategies ? findStrategy(strategies, strategyName) : null;

  if (!loading && !error && !strategy) {
    return (
      <AppShell>
        <StrategyNotFoundPage name={strategyName} />
      </AppShell>
    );
  }

  if (strategy?.missingResources.length > 0) {
    return (
      <AppShell>
        <StrategyConfigErrorPage strategy={strategy} env={env} />
      </AppShell>
    );
  }

  if (strategy) return <StrategyWorkspace key={strategy.name} strategy={strategy} strategies={strategies ?? []} />;

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-[100rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        {loading ? (
          <Alert role="status">Loading strategies…</Alert>
        ) : (
          <Alert kind="error" role="alert">Strategy manifest could not be loaded: {error}</Alert>
        )}
      </div>
    </AppShell>
  );
}

function UnknownPathRoute() {
  const { pathname } = useLocation();
  return (
    <AppShell>
      <StrategyNotFoundPage name={pathname.replace(/^\/+|\/+$/g, "")} />
    </AppShell>
  );
}

export function App() {
  const env = activeEnvironment(import.meta.env.DEV);
  const { strategies, error, loading } = useStrategies(env);

  return (
    <Routes>
      <Route
        path="/"
        element={(
          <AppShell>
            <StrategyListPage strategies={strategies} error={error} loading={loading} env={env} />
          </AppShell>
        )}
      />
      <Route path="/:strategyName" element={<StrategyRoute strategies={strategies} error={error} loading={loading} env={env} />} />
      <Route path="*" element={<UnknownPathRoute />} />
    </Routes>
  );
}
