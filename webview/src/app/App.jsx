import { AppShell } from "./AppShell.jsx";
import { usePathname } from "./router.jsx";
import { StrategyWorkspace } from "./StrategyWorkspace.jsx";
import { StrategyListPage } from "../features/strategies/StrategyListPage.jsx";
import { StrategyConfigErrorPage, StrategyNotFoundPage } from "../features/strategies/StrategyStatusPages.jsx";
import { useStrategies } from "../features/strategies/use-strategies.js";
import { activeEnvironment, findStrategy } from "../features/strategies/lib/manifest.js";
import { Alert } from "../shared/components/Alert.jsx";

function strategyNameFromPathname(pathname) {
  const trimmed = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  if (trimmed === "/") return null;
  const segment = trimmed.slice(1);
  if (segment.includes("/")) return undefined;
  try {
    return decodeURIComponent(segment);
  } catch {
    return undefined;
  }
}

export function App() {
  const pathname = usePathname();
  const env = activeEnvironment(import.meta.env.DEV);
  const { strategies, error, loading } = useStrategies(env);
  const strategyName = strategyNameFromPathname(pathname);

  if (strategyName === null) {
    return (
      <AppShell>
        <StrategyListPage strategies={strategies} error={error} loading={loading} env={env} />
      </AppShell>
    );
  }

  const strategy = strategies ? findStrategy(strategies, strategyName) : null;

  if (!loading && !error && !strategy) {
    return (
      <AppShell>
        <StrategyNotFoundPage name={strategyName} />
      </AppShell>
    );
  }

  if (strategy && strategy.missingResources.length > 0) {
    return (
      <AppShell>
        <StrategyConfigErrorPage strategy={strategy} env={env} />
      </AppShell>
    );
  }

  if (strategy) {
    return <StrategyWorkspace key={strategy.name} strategy={strategy} />;
  }

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
