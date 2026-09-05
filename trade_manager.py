"""Polling runtime for the trading agent."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable

_DATE_RANGE_PATTERN = re.compile(r"^[1-9]\d*[DWMY]$", re.IGNORECASE)
_SUPPORTED_STRATEGIES = frozenset({"pinbar-trading-strategy", "moving-average-trading-strategy", "trendline-trading-strategy"})


@dataclass(frozen=True)
class TradingRunConfig:
    symbol: str
    date_range: str
    strategy: str
    poll_seconds: int = 60
    decision_log: str = "agent_decisions.jsonl"
    magic: int = 0
    comment: str = "trend-agent"

    def __post_init__(self):
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string.")
        if not isinstance(self.date_range, str) or not self.date_range.strip():
            raise ValueError("date_range must be a non-empty string.")
        if not _DATE_RANGE_PATTERN.fullmatch(self.date_range):
            raise ValueError("date_range must be a relative lookback such as 3D, 2W, 5M, or 1Y.")
        if not isinstance(self.strategy, str) or not self.strategy.strip():
            raise ValueError("strategy must be a non-empty string.")
        if self.strategy not in _SUPPORTED_STRATEGIES:
            raise ValueError("strategy must name an available strategy skill.")
        if not isinstance(self.poll_seconds, int) or isinstance(self.poll_seconds, bool) or self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be a positive integer.")
        if not isinstance(self.decision_log, str) or not self.decision_log.strip():
            raise ValueError("decision_log must be a non-empty string.")
        if not isinstance(self.magic, int) or isinstance(self.magic, bool):
            raise ValueError("magic must be an integer.")
        if not isinstance(self.comment, str):
            raise ValueError("comment must be a string.")


def load_trading_config(path: str | Path) -> TradingRunConfig:
    """Load the autonomous-agent runtime configuration from JSON."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Unable to read agent configuration JSON.") from error
    if not isinstance(data, dict):
        raise ValueError("Agent configuration must be a JSON object.")
    required = ("symbol", "date_range", "strategy", "magic", "comment", "poll_seconds", "decision_log")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Agent configuration is missing required field: {missing[0]}.")
    return TradingRunConfig(
        symbol=data["symbol"],
        date_range=data["date_range"],
        strategy=data["strategy"],
        decision_log=data["decision_log"],
        magic=data["magic"],
        comment=data["comment"],
        poll_seconds=data["poll_seconds"],
    )

class TradeExecutionGuard:
    """Allows placement only for the active configured symbol."""

    def __init__(self):
        self.config: TradingRunConfig | None = None

    def configure(self, config: TradingRunConfig) -> None:
        self.config = config

    def disable(self) -> None:
        self.config = None

    def placement_error(self, symbol: str) -> str | None:
        if self.config is None:
            return "Trading has not been configured."
        if symbol != self.config.symbol:
            return "Trades may only be placed for the configured symbol."
        return None


def _messages(result: Any) -> list[Any]:
    return result.get("messages", []) if isinstance(result, dict) else []


def _content(result: Any) -> str:
    messages = _messages(result)
    if not messages:
        return ""
    content = getattr(messages[-1], "content", "")
    if isinstance(content, list):
        return "\n".join(block.get("text", "") for block in content if isinstance(block, dict))
    return str(content)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    as_dict = getattr(value, "_asdict", None)
    if callable(as_dict):
        return _json_safe(as_dict())
    return str(value)


def tool_events(result: Any) -> list[dict[str, Any]]:
    """Normalize tool calls and tool results returned by the agent runtime."""
    events = []
    for message in _messages(result):
        for call in getattr(message, "tool_calls", []) or []:
            events.append(
                {
                    "type": "tool_call",
                    "id": call.get("id"),
                    "name": call.get("name"),
                    "args": _json_safe(call.get("args", {})),
                }
            )
        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id is not None:
            events.append(
                {
                    "type": "tool_result",
                    "id": tool_call_id,
                    "name": getattr(message, "name", None),
                    "content": _json_safe(getattr(message, "content", None)),
                }
            )
    return events


def append_decision_log(path: str | Path, record: dict[str, Any]) -> None:
    """Append one JSON-safe decision record without replacing previous history."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(record), separators=(",", ":")) + "\n")


def format_cycle_report(record: dict[str, Any]) -> str:
    """Return only the agent's compact, human-readable cycle report for the console."""
    return record["report"]


def run_trading_loop(
    agent: Any,
    config: TradingRunConfig,
    account_snapshot: Callable[[], Any],
    open_trades: Callable[[str], Any],
    execution_guard: TradeExecutionGuard,
    sleep: Callable[[float], None],
    audit_log_writer: Callable[[str | Path, dict[str, Any]], None] = append_decision_log,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    emit: Callable[[str], None] = print,
) -> dict[str, str]:
    """Run autonomous market-analysis and trade-management cycles until interrupted."""
    execution_guard.configure(config)

    cycle = 0
    try:
        while True:
            cycle += 1
            cycle_time = now().astimezone(timezone.utc)
            account = account_snapshot()
            current_trades = open_trades(config.symbol)
            prompt = (
                "Autonomous forex-trading cycle. Read the market-data and strategies skills, then use "
                "only the configured strategy for the final decision. Do not evaluate, select, load, or "
                "combine any other strategy. Name the configured strategy in the Market or Reason line. "
                "That strategy is the sole source of truth for price-data tool choice, indicators, "
                "timeframes, freshness, entries, exits, and trade management. Retrieve only the selected "
                "strategy's required price data before any trading decision. "
                "Return the required compact decision report whether or not an entry is supported.\n"
                f"symbol={config.symbol}; date_range={config.date_range}; strategy={config.strategy}; magic={config.magic};\n"
                f"account_snapshot={account}\n"
                f"open_trades={current_trades}\n"
                "Do not invent market data, indicator values, prices, trade results, or open trades."
            )
            result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
            content = _content(result) or "Agent did not return a decision report."
            timestamp = cycle_time.isoformat()
            record = {
                "timestamp": timestamp,
                "cycle": cycle,
                "symbol": config.symbol,
                "date_range": config.date_range,
                "strategy": config.strategy,
                "poll_seconds": config.poll_seconds,
                "account": account,
                "open_trades": current_trades,
                "report": content,
                "tool_events": tool_events(result),
            }
            audit_log_writer(config.decision_log, record)
            emit(format_cycle_report(record))
            sleep(config.poll_seconds)
    except KeyboardInterrupt:
        return {"status": "stopped", "reason": "Trading loop stopped by user."}
    finally:
        execution_guard.disable()
