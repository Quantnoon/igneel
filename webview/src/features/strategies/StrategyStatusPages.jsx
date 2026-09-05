import { Link } from "../../app/router.jsx";
import { Alert } from "../../shared/components/Alert.jsx";

function BackToStrategiesLink() {
  return (
    <Link
      to="/"
      className="mt-5 inline-flex h-10 items-center justify-center rounded-lg border border-foreground/15 bg-muted/70 px-4 text-sm font-medium transition-colors hover:bg-muted outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      Back to strategies
    </Link>
  );
}

export function StrategyNotFoundPage({ name }) {
  return (
    <div className="mx-auto w-full max-w-[100rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="grid gap-1">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">Strategy not found</h2>
        <p className="text-sm text-muted-foreground">
          No strategy named &quot;{name}&quot; exists in strategies.json.
        </p>
      </div>
      <BackToStrategiesLink />
    </div>
  );
}

export function StrategyConfigErrorPage({ strategy, env }) {
  return (
    <div className="mx-auto w-full max-w-[100rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="grid gap-3">
        <div className="grid gap-1">
          <h2 className="break-words font-heading text-2xl font-semibold tracking-tight">{strategy.name}</h2>
          <p className="text-sm text-muted-foreground">This strategy is not configured for the {env} environment yet.</p>
        </div>
        <Alert kind="error" role="alert">
          Strategy &quot;{strategy.name}&quot; is missing {env} resource URLs for:{" "}
          {strategy.missingResources.join(", ")}. Populate the {env} entries in strategies.json to enable
          this strategy.
        </Alert>
      </div>
      <BackToStrategiesLink />
    </div>
  );
}
