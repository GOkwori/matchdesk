"""Write (or check) the frontend demo export generated from the canonical match.

Usage: python -m scripts.export_demo_data [--check]
--check fails when the committed JSON differs from a fresh deterministic export.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from matchdesk.domain.demo_export import build_demo_export

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "apps/web/src/studio/generated/nbr-riv.json"


def render() -> str:
    """Return the canonical JSON text for the export."""
    return json.dumps(build_demo_export(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    """Write the export, or compare it with the committed file in --check mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if the committed export is stale"
    )
    args = parser.parse_args()
    text = render()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != text:
            print(f"STALE: {TARGET.relative_to(ROOT)} differs from a fresh export")
            return 1
        print(f"OK: {TARGET.relative_to(ROOT)} is current")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
