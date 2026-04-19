from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solr_metal.models import ArtifactRef


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _directory(self, test_id: str) -> Path:
        path = self.root / "artifacts" / test_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_text(self, test_id: str, name: str, content: str) -> ArtifactRef:
        path = self._directory(test_id) / name
        path.write_text(content, encoding="utf-8")
        return ArtifactRef(name=name, path=str(path))

    def write_json(self, test_id: str, name: str, payload: Any) -> ArtifactRef:
        path = self._directory(test_id) / name
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return ArtifactRef(name=name, path=str(path))
