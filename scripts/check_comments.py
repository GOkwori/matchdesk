"""Require documentation on authored Python modules, classes and callable definitions.

This gate checks presence, not the truth or usefulness of an explanation. Review
must still examine intent, assumptions, security boundaries and stale comments.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect_python(path: Path) -> tuple[int, list[str]]:
    """Return checked definitions and actionable missing-docstring diagnostics."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors: list[str] = []
    count = 1
    if not ast.get_docstring(tree):
        errors.append(f"{path}:1: missing module docstring")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            count += 1
            if not ast.get_docstring(node):
                errors.append(f"{path}:{node.lineno}: missing docstring for {node.name}")
    return count, errors


def main() -> int:
    """Check authored code only and leave generated schemas to their own validator."""
    files = sorted((ROOT / "backend").rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py"))
    checked = 0
    errors: list[str] = []
    for path in files:
        count, missing = inspect_python(path)
        checked += count
        errors.extend(missing)
    # TypeScript JSDoc presence is a lightweight check, not full semantic linting.
    for path in sorted((ROOT / "apps/web/src").rglob("*.tsx")):
        if not path.read_text(encoding="utf-8").lstrip().startswith("/**"):
            errors.append(f"{path}: missing file-level JSDoc")
    print(
        json.dumps(
            {
                "python_files": len(files),
                "definitions_checked": checked,
                "missing": errors,
                "human_comment_review": "required",
            },
            indent=2,
        )
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
