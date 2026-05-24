"""
Helpers for persisting install-time state used by setup and teardown flows.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


INSTALL_RECORD_FILENAME = 'install-record.json'


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stringify_path(value: str | Path | None) -> str | None:
    if value is None:
        return None
    return str(Path(value).expanduser())


def default_install_record_path(app_data_root: str | Path) -> Path:
    return Path(app_data_root).expanduser() / INSTALL_RECORD_FILENAME


def load_install_record(record_path: str | Path) -> dict[str, Any] | None:
    path = Path(record_path).expanduser()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def upsert_install_record(
    record_path: str | Path,
    *,
    install_mode: str | None = None,
    path_updates: dict[str, str | Path | None] | None = None,
    feature_updates: dict[str, bool | None] | None = None,
) -> dict[str, Any]:
    path = Path(record_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    record = load_install_record(path) or {
        'schema_version': 1,
        'created_at_utc': _utc_timestamp(),
        'paths': {},
        'features': {},
    }
    record['schema_version'] = 1
    record['updated_at_utc'] = _utc_timestamp()

    if install_mode is not None:
        record['install_mode'] = install_mode

    if path_updates:
        paths = record.setdefault('paths', {})
        for key, value in path_updates.items():
            if value is None:
                paths.pop(key, None)
            else:
                paths[key] = _stringify_path(value)

    if feature_updates:
        features = record.setdefault('features', {})
        for key, value in feature_updates.items():
            if value is None:
                features.pop(key, None)
            else:
                features[key] = bool(value)

    path.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return record


def remove_install_record(record_path: str | Path) -> bool:
    path = Path(record_path).expanduser()
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True
