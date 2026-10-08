"""Validate authored documentation paths, UTF-8 encoding and public/private boundaries."""
from __future__ import annotations
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def markdown_errors(path: Path, root: Path) -> list[str]:
    """Check local file links without making network requests or modifying prose."""
    errors: list[str] = []
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(f"{path}: UTF-8 BOM is not allowed")
    text = raw.decode("utf-8")
    # Fenced command examples are not Markdown links and must not be misclassified.
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", prose):
        parsed = urlsplit(link)
        if parsed.scheme or not parsed.path:
            continue
        target = (path.parent / unquote(parsed.path)).resolve()
        if not target.is_relative_to(root.resolve()) or not target.exists():
            errors.append(f"{path}: broken or out-of-repository link: {link}")
    return errors


def main() -> int:
    """Fail when required documents or relative targets are absent."""
    required = json.loads((ROOT / "docs/required-docs.json").read_text(encoding="utf-8"))
    errors = [f"Missing required document: {name}" for name in required if not (ROOT / name).is_file()]
    paths = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    for path in paths:
        if path.is_file():
            errors.extend(markdown_errors(path, ROOT))
    for path in ROOT.rglob("*IMPLEMENTATION_PROMPT*"):
        errors.append(f"Private execution brief found in project: {path}")
    print(json.dumps({"documents_checked": len(paths), "errors": errors}, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
