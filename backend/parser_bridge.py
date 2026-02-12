from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .schemas import TaskRecord


class MppParseError(RuntimeError):
    pass


def parse_mpp(path: Path, parser_jar: Path) -> list[TaskRecord]:
    if not path.exists():
        raise MppParseError(f"File not found: {path}")
    if not parser_jar.exists():
        raise MppParseError(
            f"Parser JAR not found: {parser_jar}. Build it first via java-parser/README.md"
        )

    result = subprocess.run(
        ["java", "-jar", str(parser_jar), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise MppParseError(result.stderr.strip() or "Unknown Java parser error")

    payload = json.loads(result.stdout)
    return [TaskRecord.model_validate(item) for item in payload["tasks"]]
