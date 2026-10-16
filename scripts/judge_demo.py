#!/usr/bin/env python3
"""Print the deterministic synthetic judge path without network or persistence."""

from __future__ import annotations

import json

from matchdesk.domain.judge_golden_path import build_judge_golden_path


def main() -> None:
    """Emit a bounded, inspectable stdout manifest; never write or publish."""
    print(json.dumps(build_judge_golden_path(), sort_keys=True, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
