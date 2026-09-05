---
name: strategies
description: Route autonomous forex market analysis and trade decisions to the active strategy skill.
---

# Trading Strategies

Use a strategy skill as the sole source of truth for market analysis, entry, exit, risk/reward, and trade-management decisions. The cycle context supplies `strategy`; read only the mapped strategy below. State that exact configured name in the `Market` or `Reason` field. Do not evaluate, select, load, or combine rules from another strategy. Do not combine rules across strategies.

Available strategy:

- `strategy=pinbar-trading-strategy`: read `/skills/strategies/pinbar-trading-strategy/SKILL.md`.
- `strategy=moving-average-trading-strategy`: read `/skills/strategies/moving-average-trading-strategy/SKILL.md`.
- `strategy=trendline-trading-strategy`: read `/skills/strategies/trendline-trading-strategy/SKILL.md`.

If `strategy` is missing or does not match one of these values, return `Decision: no signal` and state that the configured strategy is invalid. Do not use another strategy as a fallback.
