"""Export deterministic schemas and reject drift against the reviewed contract files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from matchdesk.api.app import create_app
from matchdesk.domain.models import (
    ApprovalBinding,
    Claim,
    EvidenceRecord,
    Location,
    MatchEvent,
    MatchWindow,
    MetricAssertion,
    Subject,
    VerificationResult,
)

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    Location,
    MatchEvent,
    MatchWindow,
    Subject,
    MetricAssertion,
    Claim,
    EvidenceRecord,
    VerificationResult,
    ApprovalBinding,
)


def expected_exports() -> dict[str, str]:
    """Return deterministic files; exclude wall-clock values from schema identities."""
    exports: dict[str, str] = {}
    for model in MODELS:
        exports[f"{model.__name__}.v1.json"] = (
            json.dumps(
                model.model_json_schema(),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    exports["openapi.json"] = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
    manifest = {
        "schema_version": "1.0",
        "files": {
            name: hashlib.sha256(text.encode()).hexdigest() for name, text in exports.items()
        },
    }
    exports["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    return exports


def check_exports() -> list[str]:
    """List missing or changed schemas; never refresh a baseline during validation."""
    errors = []
    expected = expected_exports()
    for name, text in expected.items():
        path = ROOT / "contracts" / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            errors.append(f"Contract drift: {name}")
    for path in (ROOT / "contracts").glob("*.json"):
        if path.name not in expected:
            errors.append(f"Unexpected contract: {path.name}")
    return errors


def main() -> int:
    """Write contracts only on explicit request; default execution checks drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="Explicitly create/update reviewed baselines"
    )
    args = parser.parse_args()
    if args.write:
        (ROOT / "contracts").mkdir(exist_ok=True)
        for name, text in expected_exports().items():
            (ROOT / "contracts" / name).write_text(text, encoding="utf-8")
        print("Exported schema version 1.0; review changes before committing.")
        return 0
    errors = check_exports()
    print("\n".join(errors) if errors else "Contract snapshots match.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
