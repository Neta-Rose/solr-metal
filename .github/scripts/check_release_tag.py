from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path


def main() -> int:
    tag = os.environ["GITHUB_REF_NAME"]
    pyproject = Path("pyproject.toml")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    version = data["project"]["version"]
    expected = f"v{version}"
    if tag != expected:
        print(f"release tag mismatch: got {tag}, expected {expected}", file=sys.stderr)
        return 1
    print(f"release tag matches package version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
