from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SM_",
        env_file=".env",
        extra="ignore",
    )

    definitions_dir: Path = Path("catalog/definitions")
    output_root: Path = Path("runs")
    pause_image: str = "registry.k8s.io/pause:3.10"
    dns_image: str = "busybox:1.36.1"
    pvc_size: str = "1Gi"
    rich_tracebacks: bool = True
    app_name: str = Field(default="solr-metal")

    def default_run_dir(self, now: datetime | None = None) -> Path:
        stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H-%M-%SZ"
        )
        return self.output_root / stamp
