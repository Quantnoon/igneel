export const MANIFEST_PATH = "strategies/strategies.json";
export const RESOURCE_FIELDS = ["df", "config", "result"];

const STRATEGY_ID = /^strategies\/([a-z0-9]+(?:[-_][a-z0-9]+)*)$/;

export function activeEnvironment(isDevelopment) {
  return isDevelopment ? "development" : "production";
}

function missingResourceFields(resources) {
  return RESOURCE_FIELDS.filter((field) => {
    const value = resources?.[field];
    if (field === "df") {
      return !Array.isArray(value) || value.length === 0 || value.some((entry) => (
        !entry || typeof entry !== "object" || Array.isArray(entry)
        || typeof entry.name !== "string" || !entry.name.trim()
        || typeof entry.path !== "string" || !entry.path.trim()
      ));
    }
    return typeof value !== "string" || !value.trim();
  });
}

export function parseStrategyManifest(text, env) {
  let entries;
  try {
    entries = JSON.parse(text);
  } catch {
    throw new Error("strategies.json is not valid JSON.");
  }
  if (!Array.isArray(entries)) {
    throw new Error("strategies.json must contain an array of strategies.");
  }

  const routeNames = new Set();
  return entries.map((entry, index) => {
    const label = `strategies.json entry ${index}`;
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      throw new Error(`${label} must be an object.`);
    }
    const { name, env: environments } = entry;
    if (typeof name !== "string" || !name.trim()) {
      throw new Error(`${label} must have a non-empty name.`);
    }
    const match = STRATEGY_ID.exec(name);
    if (!match) {
      throw new Error(
        `Strategy name "${name}" must use the strategies/<name> format.`,
      );
    }
    const routeName = match[1];
    if (routeNames.has(routeName)) {
      throw new Error(`Strategy name "${routeName}" is duplicated. Strategy route names must be unique.`);
    }
    routeNames.add(routeName);
    if (!environments || typeof environments !== "object" || Array.isArray(environments)) {
      throw new Error(`Strategy "${name}" must declare an "env" object.`);
    }

    const activeResources = environments[env];
    const resources = {
      df: Array.isArray(activeResources?.df)
        ? activeResources.df
          .filter((entry) => entry && typeof entry === "object" && !Array.isArray(entry))
          .map((entry) => ({
            name: typeof entry.name === "string" ? entry.name.trim() : "",
            path: typeof entry.path === "string" ? entry.path.trim() : "",
          }))
        : [],
      config: typeof activeResources?.config === "string" ? activeResources.config.trim() : "",
      result: typeof activeResources?.result === "string" ? activeResources.result.trim() : "",
    };
    return {
      name: routeName,
      resourceIdentity: name,
      env,
      resources,
      missingResources: missingResourceFields(activeResources),
    };
  });
}

export function isAccessible(strategy) {
  return strategy.missingResources.length === 0;
}

export function findStrategy(strategies, name) {
  return strategies.find((strategy) => strategy.name === name) ?? null;
}
