import json
from threading import Lock
from . import config

_lock = Lock()


def _read() -> dict:
    if not config.JOBS_FILE.exists():
        return {}
    try:
        return json.loads(config.JOBS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write(data: dict) -> None:
    config.JOBS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def create(audio_id: str, **fields) -> dict:
    with _lock:
        data = _read()
        data[audio_id] = {"audio_id": audio_id, **fields}
        _write(data)
        return data[audio_id]


def update(audio_id: str, **fields) -> dict:
    with _lock:
        data = _read()
        if audio_id not in data:
            raise KeyError(audio_id)
        data[audio_id].update(fields)
        _write(data)
        return data[audio_id]


def get(audio_id: str) -> dict | None:
    with _lock:
        return _read().get(audio_id)
