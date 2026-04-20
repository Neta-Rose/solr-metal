from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, get_args, get_origin

from platformdirs import PlatformDirs
from pydantic import BaseModel, Field, TypeAdapter


class Settings(BaseModel):
    app_name: str = "solr-metal"
    distribution_name: str = "solr-metal"
    output_root: Path = Path("runs")
    extra_definition_dirs: list[Path] = Field(default_factory=list)
    kubeconfig: Path | None = None
    pause_image: str = "registry.k8s.io/pause:3.10"
    dns_image: str = "busybox:1.36.1"
    pvc_size: str = "1Gi"
    rich_tracebacks: bool = True
    version_check_enabled: bool = False
    version_source_type: str = "pypi-json"
    version_source_url: str | None = None
    version_source_package: str = "solr-metal"
    version_check_timeout_seconds: float = 2.5

    def default_run_dir(self, now: datetime | None = None) -> Path:
        stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H-%M-%SZ"
        )
        return self.output_root / stamp


@dataclass(frozen=True)
class LoadedSettings:
    settings: Settings
    config_files: tuple[Path, ...]


def load_settings(
    config_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> LoadedSettings:
    merged: dict[str, Any] = {}
    used_files: list[Path] = []
    for path in config_file_candidates(config_path):
        if not path.exists():
            continue
        merged.update(load_config_file(path))
        used_files.append(path)

    merged.update(load_env_overrides(Settings))
    for key, value in (cli_overrides or {}).items():
        if value is not None:
            merged[key] = value

    return LoadedSettings(settings=Settings.model_validate(merged), config_files=tuple(used_files))


def config_file_candidates(explicit: Path | None) -> list[Path]:
    dirs = PlatformDirs("solr-metal", "solr-metal")
    candidates = [
        Path(dirs.site_config_path) / "config.toml",
        Path(dirs.user_config_path) / "config.toml",
        Path.cwd() / ".solr-metal.toml",
    ]
    if explicit:
        candidates.append(explicit)
    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(candidate)
    return deduped


def load_config_file(path: Path) -> dict[str, Any]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if "tool" in data and "solr-metal" in data["tool"]:
        return dict(data["tool"]["solr-metal"])
    if "solr-metal" in data:
        return dict(data["solr-metal"])
    return dict(data)


def load_env_overrides(model: type[BaseModel]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for field_name, field_info in model.model_fields.items():
        env_name = f"SM_{field_name.upper()}"
        raw_value = os.environ.get(env_name)
        if raw_value is None:
            continue
        overrides[field_name] = parse_env_value(field_info.annotation, raw_value)
    return overrides


def parse_env_value(annotation: Any, raw_value: str) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is list and args:
        try:
            payload = json.loads(raw_value)
            if isinstance(payload, list):
                return [TypeAdapter(args[0]).validate_python(item) for item in payload]
        except json.JSONDecodeError:
            pass
        return [TypeAdapter(args[0]).validate_python(item) for item in raw_value.split(os.pathsep) if item]

    if origin is None and annotation is bool:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    if origin is None and annotation in {int, float, str, Path}:
        return TypeAdapter(annotation).validate_python(raw_value)

    if origin is not None and type(None) in args:
        non_none = [arg for arg in args if arg is not type(None)]
        if not non_none:
            return raw_value
        return parse_env_value(non_none[0], raw_value)

    return raw_value
