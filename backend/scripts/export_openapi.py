"""Dump OpenAPI JSON for the TypeScript client (D37)."""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JOB_WORKER_ENABLED", "false")

from app.core.config import get_settings
from app.main import app

get_settings.cache_clear()


def main() -> None:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    dest.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
