"""Stable content identity for immutable, serialisable contract records."""
from __future__ import annotations

import hashlib
import json

from matchdesk.domain.models import Contract


def canonical_bytes(record: Contract) -> bytes:
    """Encode model content deterministically as sorted, compact UTF-8 JSON.

    Model defaults are retained so omitted defaults and explicit defaults share
    an identity. This is a version-1 application encoding, not RFC 8785 JCS.
    Any future change to encoding rules needs a format version and migration.
    """
    return json.dumps(
        record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def content_digest(record: Contract) -> str:
    """Return SHA-256 of contract content; it proves identity, not factual accuracy."""
    return hashlib.sha256(canonical_bytes(record)).hexdigest()
