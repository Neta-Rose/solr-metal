from __future__ import annotations

import json
import tomllib
import urllib.request
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
from typing import Protocol

from packaging.version import Version


@dataclass(frozen=True)
class VersionStatus:
    current: str
    latest: str | None
    source: str
    url: str | None = None

    @property
    def update_available(self) -> bool:
        if not self.latest:
            return False
        return Version(self.latest) > Version(self.current)


class VersionSource(Protocol):
    def fetch_latest(self, package_name: str, timeout_seconds: float) -> VersionStatus: ...


class DisabledVersionSource:
    def fetch_latest(self, package_name: str, timeout_seconds: float) -> VersionStatus:
        return VersionStatus(current=current_version(package_name), latest=None, source="disabled")


class PyPIJsonVersionSource:
    def __init__(self, base_url: str = "https://pypi.org/pypi") -> None:
        self.base_url = base_url.rstrip("/")

    def fetch_latest(self, package_name: str, timeout_seconds: float) -> VersionStatus:
        url = f"{self.base_url}/{package_name}/json"
        payload = _fetch_json(url, timeout_seconds)
        latest = payload["info"]["version"]
        return VersionStatus(current=current_version(package_name), latest=latest, source="pypi-json", url=url)


class SimpleApiVersionSource:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def fetch_latest(self, package_name: str, timeout_seconds: float) -> VersionStatus:
        url = f"{self.base_url}/{package_name}/"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.pypi.simple.v1+json",
                "User-Agent": "solr-metal/version-check",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        versions = payload.get("versions", [])
        latest = str(max(Version(item) for item in versions)) if versions else None
        return VersionStatus(current=current_version(package_name), latest=latest, source="simple-api", url=url)


class StaticJsonVersionSource:
    def __init__(self, url: str) -> None:
        self.url = url

    def fetch_latest(self, package_name: str, timeout_seconds: float) -> VersionStatus:
        payload = _fetch_json(self.url, timeout_seconds)
        latest = payload["version"]
        return VersionStatus(current=current_version(package_name), latest=latest, source="static-json", url=self.url)


def current_version(package_name: str = "solr-metal") -> str:
    try:
        return distribution_version(package_name)
    except PackageNotFoundError:
        pyproject = find_pyproject()
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return data["project"]["version"]


def resolve_version_source(
    source_type: str,
    package_name: str,
    source_url: str | None,
) -> VersionSource:
    if source_type == "disabled":
        return DisabledVersionSource()
    if source_type == "pypi-json":
        return PyPIJsonVersionSource(source_url or "https://pypi.org/pypi")
    if source_type == "simple-api":
        if not source_url:
            raise ValueError("version_source_url is required for simple-api version checks")
        return SimpleApiVersionSource(source_url)
    if source_type == "static-json":
        if not source_url:
            raise ValueError("version_source_url is required for static-json version checks")
        return StaticJsonVersionSource(source_url)
    raise ValueError(f"unsupported version source {source_type!r}")


def check_latest_version(
    source_type: str,
    package_name: str,
    source_url: str | None,
    timeout_seconds: float,
) -> VersionStatus:
    source = resolve_version_source(source_type, package_name, source_url)
    return source.fetch_latest(package_name, timeout_seconds)


def _fetch_json(url: str, timeout_seconds: float) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "solr-metal/version-check"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def find_pyproject() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        candidate = parent / "pyproject.toml"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("pyproject.toml not found")
