import json
from datetime import datetime, timezone
from threading import Lock
from . import config

_lock = Lock()


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _read() -> dict:
    if not config.USAGE_FILE.exists():
        return {"month": _current_month(), "tokens_used": 0}
    try:
        data = json.loads(config.USAGE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    if data.get("month") != _current_month():
        data = {"month": _current_month(), "tokens_used": 0}
    return data


def _write(data: dict) -> None:
    config.USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def add_tokens(n: int) -> None:
    if n <= 0:
        return
    with _lock:
        data = _read()
        data["tokens_used"] += n
        _write(data)


def status() -> dict:
    with _lock:
        data = _read()
    used = data["tokens_used"]
    budget = config.MONTHLY_TOKEN_BUDGET
    remaining = max(budget - used, 0)
    percent_remaining = round((remaining / budget) * 100) if budget else 0
    return {
        "month": data["month"],
        "budget": budget,
        "used": used,
        "remaining": remaining,
        "percent_remaining": percent_remaining,
    }
