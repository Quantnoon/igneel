import json
import math
import re
from collections.abc import Mapping
from datetime import date, datetime
import pandas as pd

WEBVIEW_TRADE_FIELDS = (
    "position",
    "entry",
    "exit",
    "sl",
    "tp",
    "open_time",
    "close_time",
    "result",
    "pnl",
    "pnl_dollar",
    "pnl_currency",
    "balance_before",
    "balance_after",
    "session",
    "day",
    "skipped",
    "skip_reason",
)

def _chart_indicators(indicator_list):
    grouped = {}
    for entry in indicator_list:
        indicator_type = entry["indicator"]
        timeframe = entry["timeframe"]
        outputs = entry.get("outputs") or _default_outputs(indicator_type)
        columns = [f"{output}_{timeframe}" for output in outputs]
        grouped.setdefault(indicator_type, []).extend(columns)
    return [
        {"type": indicator_type, "columns": columns}
        for indicator_type, columns in grouped.items()
    ]


def _default_outputs(indicator_type):
    outputs = {
        "BBANDS": ["bbands_upper", "bbands_middle", "bbands_lower"],
        "SUPPLY_ZONE": ["supply_low", "supply_high"],
        "DEMAND_ZONE": ["demand_low", "demand_high"],
        "SUPPORT_ZONE": ["support_low", "support_high"],
        "RESISTANCE_ZONE": ["resistance_low", "resistance_high"],
        "BULLISH_FVG": ["bullish_fvg_low", "bullish_fvg_high"],
        "BEARISH_FVG": ["bearish_fvg_low", "bearish_fvg_high"],
    }
    if indicator_type in outputs:
        return outputs[indicator_type]
    return [indicator_type.lower()]


def _strategy_slug(strategy_name):
    slug = re.sub(r"[^a-z0-9]+", "-", str(strategy_name).strip().lower()).strip("-")
    if not slug:
        raise ValueError("Each strategy_list entry must have a name that produces a non-empty URL-safe slug.")
    return slug


def _webview_strategies(strategy_entries):
    strategies = []
    slugs = set()
    for entry in strategy_entries:
        if not isinstance(entry, tuple) or len(entry) < 2 or not isinstance(entry[0], str) or not callable(entry[1]):
            raise ValueError("Each strategy_list entry must be a tuple of (name, callback[, exit_callback]).")
        slug = _strategy_slug(entry[0])
        if slug in slugs:
            raise ValueError(f"Strategy names produce duplicate WebView slug: {slug}")
        slugs.add(slug)
        strategies.append({"name": entry[0], "slug": slug, "callback": entry[1]})
    if not strategies:
        raise ValueError("strategy_list must contain at least one strategy.")
    return strategies


def _json_value(value):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_value(value.item())
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


def _trade_records(trade_log):
    if trade_log is None:
        return []
    if isinstance(trade_log, pd.DataFrame):
        records = trade_log.to_dict(orient="records")
    elif isinstance(trade_log, list):
        records = trade_log
    else:
        raise ValueError("Backtest report trade_log must be a pandas DataFrame or list of records.")
    return [_json_value(record) for record in records if isinstance(record, Mapping)]


def _report_payload(report):
    payload = _json_value(report if isinstance(report, Mapping) else {})
    payload["trade_log"] = _trade_records(report.get("trade_log") if isinstance(report, Mapping) else None)
    return payload


def _chart_data_with_trades(frame, trades):
    if "time" not in frame.columns:
        raise ValueError("Price data must contain a time column for WebView output.")
    chart_data = frame.copy()
    for field in WEBVIEW_TRADE_FIELDS:
        chart_data[f"backtest_{field}"] = None
    chart_data["backtest_trade_id"] = None

    candle_times = pd.to_datetime(chart_data["time"], utc=True, errors="coerce")
    for trade_id, trade in enumerate(trades):
        open_time = pd.to_datetime(trade.get("open_time"), utc=True, errors="coerce")
        if pd.isna(open_time):
            continue
        matching_rows = chart_data.index[candle_times == open_time]
        if len(matching_rows) == 0:
            continue
        row = matching_rows[0]
        chart_data.at[row, "backtest_trade_id"] = trade_id
        for field in WEBVIEW_TRADE_FIELDS:
            chart_data.at[row, f"backtest_{field}"] = trade.get(field)
    return chart_data


def _load_manifest(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    if not isinstance(manifest, list):
        raise ValueError("webview/strategies/strategies.json must contain an array.")
    return manifest


def _update_manifest(manifest, slug, symbols):
    slug = f"strategies/{slug}"
    df = [
        {
            "name": symbol,
            "path": f"{slug}/{symbol}_df.csv"
        }
        for symbol in symbols
    ]
    resources = {
        "df": df,
        "config": f"{slug}/config.json",
        "result": f"{slug}/result.json",
    }
    for entry in manifest:
        if isinstance(entry, dict) and entry.get("name") == slug:
            environments = entry.get("env")
            if not isinstance(environments, dict):
                environments = {}
            entry["env"] = {**environments, "development": resources}
            return
    manifest.append({"name": slug, "env": {"development": resources, "production": {}}})


def write_webview_resources(webview_dir, symbols, strategy_entries, result, frames, entry_tf, indicators):
    webview_dir.mkdir(exist_ok=True)
    manifest_path = webview_dir / "strategies.json"
    manifest = _load_manifest(manifest_path)

    strategy_name = strategy_entries[0]

    chart_config = {
        "symbols": symbols,
        "entry_tf": entry_tf,
        "indicators": _chart_indicators(indicators),
    }

    result_dump = {}
    reports = {}

    for symbol in symbols:
        result_entries = result.get(symbol, []) if isinstance(result, Mapping) else []
        results_by_name = {
            entry.get("name"): entry
            for entry in result_entries
            if isinstance(entry, Mapping) and isinstance(entry.get("name"), str)
        }
        strategy_result = results_by_name.get(strategy_name)
        if strategy_result is None:
            raise ValueError(f"Backtest did not return results for strategy: {strategy_name}")
        report = _report_payload(strategy_result.get("report"))

        reports[symbol] = report
        result_dump[symbol] = {"name": strategy_name, "report": reports[symbol]}

    strategy_dir = webview_dir / strategy_name
    strategy_dir.mkdir(exist_ok=True)
    for symbol in symbols:
        _chart_data_with_trades(frames[symbol], reports[symbol]["trade_log"]).to_csv(strategy_dir / f"{symbol}_df.csv", index=False)
    with (strategy_dir / "config.json").open("w", encoding="utf-8") as config_file:
        json.dump(chart_config, config_file, allow_nan=False)
    with (strategy_dir / "result.json").open("w", encoding="utf-8") as result_file:
        json.dump(result_dump, result_file, allow_nan=False)
    _update_manifest(manifest, strategy_name, symbols)

    with manifest_path.open("w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, indent=2)