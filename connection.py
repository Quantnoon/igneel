"""MetaTrader 5 account connection helpers."""

from typing import Any, Dict, Optional, Tuple

import MetaTrader5 as mt5


def _result(
    success: bool,
    account_info: Optional[Dict[str, Any]] = None,
    terminal_info: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "success": success,
        "account_info": account_info,
        "terminal_info": terminal_info,
        "error": error,
    }


def _error(code: Optional[int], message: str) -> Dict[str, Any]:
    return {"code": code, "message": message}


def _sanitize_message(message: str, sensitive_values: Tuple[Any, ...]) -> str:
    for value in sensitive_values:
        text = str(value) if value is not None else ""
        if text:
            message = message.replace(text, "[REDACTED]")
    return message


def _normalize_error(
    diagnostic: Any,
    fallback: str,
    sensitive_values: Tuple[Any, ...] = (),
) -> Dict[str, Any]:
    if isinstance(diagnostic, (tuple, list)) and len(diagnostic) >= 2:
        code, message = diagnostic[0], diagnostic[1]
        normalized_code = code if isinstance(code, int) and not isinstance(code, bool) else None
        if isinstance(message, str) and message:
            return _error(normalized_code, _sanitize_message(message, sensitive_values))
    return _error(None, fallback)


def _metadata_dict(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    as_dict = getattr(value, "_asdict", None)
    if callable(as_dict):
        return dict(as_dict())
    if isinstance(value, dict):
        return dict(value)
    raise TypeError("MetaTrader 5 metadata was not a mapping.")


def _validate(account_details: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not isinstance(account_details, dict):
        return None, _error(None, "account_details must be a dictionary.")

    for key in ("login", "password", "server"):
        if key not in account_details:
            return None, _error(None, "Missing required account field: %s." % key)

    login = account_details["login"]
    if not isinstance(login, int) or isinstance(login, bool):
        return None, _error(None, "login must be an integer.")
    for key in ("password", "server"):
        value = account_details[key]
        if not isinstance(value, str) or not value:
            return None, _error(None, "%s must be a non-empty string." % key)

    path = account_details.get("path")
    if "path" in account_details and (not isinstance(path, str) or not path):
        return None, _error(None, "path must be a non-empty string when supplied.")
    timeout = account_details.get("timeout")
    if "timeout" in account_details and (
        not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0
    ):
        return None, _error(None, "timeout must be a positive integer when supplied.")
    portable = account_details.get("portable")
    if "portable" in account_details and not isinstance(portable, bool):
        return None, _error(None, "portable must be a boolean when supplied.")

    return {
        "login": login,
        "password": account_details["password"],
        "server": account_details["server"],
        "path": path,
        "timeout": timeout,
        "portable": portable,
    }, None


def connect(account_details: Any) -> Dict[str, Any]:
    """Initialize MetaTrader 5 and return account and terminal metadata."""
    settings, validation_error = _validate(account_details)
    if validation_error is not None:
        return _result(False, error=validation_error)

    arguments = {
        "login": settings["login"],
        "password": settings["password"],
        "server": settings["server"],
    }
    if settings["timeout"] is not None:
        arguments["timeout"] = settings["timeout"]
    if settings["portable"] is not None:
        arguments["portable"] = settings["portable"]

    try:
        if settings["path"] is None:
            initialized = mt5.initialize(**arguments)
        else:
            initialized = mt5.initialize(settings["path"], **arguments)
        sensitive_values = (
            settings["password"],
            settings["login"],
            settings["server"],
            settings["path"],
        )
        if not initialized:
            diagnostic = _normalize_error(
                mt5.last_error(),
                "MetaTrader 5 initialization failed.",
                sensitive_values,
            )
            return _result(False, error=diagnostic)

        account_info = _metadata_dict(mt5.account_info())
        terminal_info = _metadata_dict(mt5.terminal_info())
        if account_info is None or terminal_info is None:
            diagnostic = _normalize_error(
                mt5.last_error(),
                "Account or terminal information is unavailable.",
                sensitive_values,
            )
            return _result(True, account_info, terminal_info, diagnostic)
        return _result(True, account_info, terminal_info)
    except Exception:
        return _result(False, error=_error(None, "MetaTrader 5 operation failed unexpectedly."))
