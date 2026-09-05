from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_VERSION = 1


@dataclass(frozen=True)
class FileTouch:
    path: str
    purpose: str
    action: str


@dataclass(frozen=True)
class PackageTouch:
    name: str
    manager: str
    action: str
    version: str | None = None


@dataclass(frozen=True)
class ModelTouch:
    name: str
    provider: str
    action: str


class Manifest:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {
            "manifest_version": MANIFEST_VERSION,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "files": [],
            "packages": [],
            "models": [],
        }
        if path.exists():
            loaded = json.loads(path.read_text())
            if isinstance(loaded, dict):
                self.data.update(loaded)
        self._restore_internal_keys()

    def record_file(self, touch: FileTouch) -> None:
        self._upsert_file(asdict(touch))

    def record_package(self, touch: PackageTouch) -> None:
        item = asdict(touch)
        item["_key"] = package_key(item)
        self._upsert("packages", item, "_key")

    def record_model(self, touch: ModelTouch) -> None:
        item = asdict(touch)
        item["_key"] = model_key(item)
        self._upsert("models", item, "_key")

    def save(self, dry_run: bool = False) -> None:
        self.data["updated_at"] = now_iso()
        if dry_run:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            key: [strip_internal_keys(item) for item in value] if isinstance(value, list) else value
            for key, value in self.data.items()
        }
        self.path.write_text(json.dumps(serializable, indent=2) + "\n")

    def _upsert(self, list_name: str, item: dict[str, Any], key_name: str) -> None:
        values = self.data.setdefault(list_name, [])
        if not isinstance(values, list):
            self.data[list_name] = values = []

        item["touched_at"] = now_iso()
        key = item[key_name]
        for index, existing in enumerate(values):
            if isinstance(existing, dict) and existing.get(key_name) == key:
                values[index] = {**existing, **item}
                return
        values.append(item)

    def _upsert_file(self, item: dict[str, Any]) -> None:
        values = self.data.setdefault("files", [])
        if not isinstance(values, list):
            self.data["files"] = values = []

        item["touched_at"] = now_iso()
        path = item["path"]
        for index, existing in enumerate(values):
            if isinstance(existing, dict) and existing.get("path") == path:
                action = merge_file_action(str(existing.get("action")), str(item.get("action")))
                values[index] = {**existing, **item, "action": action}
                return
        values.append(item)

    def _restore_internal_keys(self) -> None:
        packages = self.data.get("packages", [])
        if isinstance(packages, list):
            for item in packages:
                if isinstance(item, dict):
                    item["_key"] = package_key(item)

        models = self.data.get("models", [])
        if isinstance(models, list):
            for item in models:
                if isinstance(item, dict):
                    item["_key"] = model_key(item)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def strip_internal_keys(item: Any) -> Any:
    if isinstance(item, dict):
        return {key: value for key, value in item.items() if not key.startswith("_")}
    return item


def package_key(item: dict[str, Any]) -> str:
    return f"{item.get('manager')}:{item.get('name')}"


def model_key(item: dict[str, Any]) -> str:
    return f"{item.get('provider')}:{item.get('name')}"


def merge_file_action(previous: str, current: str) -> str:
    if previous == "overwrite" or current == "overwrite":
        return "overwrite"
    if previous == "create":
        return "create"
    return current
