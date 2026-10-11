#!/usr/bin/env python3
"""Import exact approved MatchDesk visual references without altering application code.

The input files are untrusted until their names, sizes, PNG checksums and source
archive structure have been checked. This tool never stages, commits or deploys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import struct
import sys
import tempfile
import zlib
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

DESIGN_ROOT = Path(__file__).resolve().parents[1]
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED = 128 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
BATCH1 = {
    f"image-gen-{n}(1).png": size
    for n, size in enumerate((2011072, 1914676, 2024796, 1969792, 2084190, 2195314, 2024214), 1)
}
_BATCH2_SIZES = (
    ("08-producer-review-queue", 370097, 235086),
    ("09-story-commentary-composer", 374416, 235139),
    ("10-review-publication-future-state", 405166, 236412),
    ("11-audience-experience", 414150, 258602),
    ("12-activity-audit-settings", 323817, 193431),
    ("13-notification-dialogue-library", 370046, 253093),
    ("14-defensive-states", 306436, 231148),
)
BATCH2 = {
    f"{name}-{viewport}.png": size
    for name, desktop, mobile in _BATCH2_SIZES
    for viewport, size in (("desktop", desktop), ("mobile", mobile))
}


class ImportValidationError(ValueError):
    """Report a rejected source or an existing file that must not be replaced."""


def checked_png(data: bytes, expected_size: int) -> tuple[int, int]:
    """Verify PNG chunks/CRCs and return dimensions without external decoders.

    A matching byte count is supporting provenance only, not proof of approval.
    Raw bytes are neither executed nor transcoded, preserving SHA-256 identity.
    """
    if len(data) != expected_size or len(data) > MAX_IMAGE_BYTES:
        raise ImportValidationError(
            f"Wrong image byte count: {len(data)}; expected {expected_size}"
        )
    if not data.startswith(PNG_MAGIC):
        raise ImportValidationError("Missing PNG signature")
    pos, chunks, width, height = 8, 0, 0, 0
    seen_data, seen_end = False, False
    while pos < len(data):
        if pos + 12 > len(data):
            raise ImportValidationError("Truncated PNG chunk")
        count = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4 : pos + 8]
        end = pos + 12 + count
        if count > MAX_IMAGE_BYTES or end > len(data):
            raise ImportValidationError("Oversized or truncated PNG chunk")
        found_crc = struct.unpack_from(">I", data, end - 4)[0]
        actual_crc = zlib.crc32(data[pos + 4 : end - 4]) & 0xFFFFFFFF
        if found_crc != actual_crc:
            raise ImportValidationError(f"Invalid PNG CRC in {kind!r}")
        if chunks == 0:
            if kind != b"IHDR" or count != 13:
                raise ImportValidationError("PNG must start with a 13-byte IHDR")
            width, height = struct.unpack_from(">II", data, pos + 8)
            if not (1 <= width <= 12000 and 1 <= height <= 12000):
                raise ImportValidationError("PNG dimensions outside allowed range")
        elif kind == b"IHDR":
            raise ImportValidationError("Repeated IHDR")
        if kind == b"IDAT":
            seen_data = True
        if kind == b"IEND":
            if count != 0 or end != len(data):
                raise ImportValidationError("Invalid IEND or trailing bytes")
            seen_end = True
            break
        pos = end
        chunks += 1
        if chunks > 10000:
            raise ImportValidationError("Excessive PNG chunk count")
    if not (seen_data and seen_end):
        raise ImportValidationError("Missing PNG data or end marker")
    return width, height


def checked_archive_name(name: str) -> str:
    """Reject absolute, traversal, Windows-style and ambiguous ZIP entry paths."""
    if (not name or name.startswith("/") or "\\" in name or
            any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))):
        raise ImportValidationError(f"Unsafe ZIP member path: {name!r}")
    return PurePosixPath(name).name


def inspect_batch2(archive: Path) -> dict[str, tuple[bytes, str]]:
    """Read only the fourteen approved PNGs; never extract ZIP paths to disk."""
    if not archive.is_file() or archive.is_symlink():
        raise ImportValidationError("Batch 2 ZIP not found or is a symbolic link")
    if archive.stat().st_size > MAX_ARCHIVE_UNCOMPRESSED:
        raise ImportValidationError("Batch 2 ZIP exceeds archive size limit")
    discovered: dict[str, tuple[bytes, str]] = {}
    try:
        with ZipFile(archive) as zipped:
            members = zipped.infolist()
            if len(members) > 100:
                raise ImportValidationError("Unexpected number of ZIP members")
            if sum(entry.file_size for entry in members) > MAX_ARCHIVE_UNCOMPRESSED:
                raise ImportValidationError("Excessive total uncompressed ZIP size")
            for info in members:
                basename = checked_archive_name(info.filename)
                if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                    raise ImportValidationError("ZIP symbolic links are not permitted")
                if info.flag_bits & 1:
                    raise ImportValidationError("Encrypted ZIP members are not permitted")
                if info.is_dir():
                    continue
                if info.filename.lower().endswith(".png") and basename not in BATCH2:
                    raise ImportValidationError(f"Unrecognised PNG in ZIP: {info.filename}")
                if basename not in BATCH2:
                    continue  # Existing design-only HTML and documentation are not copied.
                if basename in discovered:
                    raise ImportValidationError(f"Duplicate PNG filename: {basename}")
                if info.file_size != BATCH2[basename] or info.file_size > MAX_IMAGE_BYTES:
                    raise ImportValidationError(f"Unexpected PNG size for {basename}")
                with zipped.open(info) as member:
                    content = member.read(MAX_IMAGE_BYTES + 1)
                checked_png(content, BATCH2[basename])
                discovered[basename] = (content, "screenshots")
    except BadZipFile as exc:
        raise ImportValidationError("Invalid or damaged Batch 2 ZIP") from exc
    missing = sorted(BATCH2.keys() - discovered.keys())
    if missing:
        raise ImportValidationError("Missing Batch 2 PNGs: " + ", ".join(missing))
    return discovered


def inspect_batch1(folder: Path) -> dict[str, tuple[bytes, str]]:
    """Read the seven confirmed concept boards, excluding similarly named drafts."""
    if not folder.is_dir() or folder.is_symlink():
        raise ImportValidationError("Batch 1 directory not found or is a symbolic link")
    discovered = {}
    for filename, expected_size in BATCH1.items():
        path = folder / filename
        if not path.is_file() or path.is_symlink():
            raise ImportValidationError(f"Missing or unsafe Batch 1 PNG: {filename}")
        if path.stat().st_size != expected_size:
            raise ImportValidationError(f"Unexpected Batch 1 size: {filename}")
        content = path.read_bytes()
        checked_png(content, expected_size)
        discovered[filename] = (content, "concepts")
    return discovered


def import_assets(
    inputs: dict[str, tuple[bytes, str]], *, root: Path, write: bool
) -> list[dict[str, object]]:
    """Preflight all destinations, then write exact PNGs and a SHA-256 audit manifest.

    Existing files are immutable; even a single conflicting file aborts the batch.
    The default dry-run reports planned items without modifying the repository.
    """
    planned = []
    for filename, (data, category) in sorted(inputs.items()):
        if category not in ("concepts", "screenshots"):
            raise ImportValidationError("Invalid asset category")
        rel = f"{category}/{filename}"
        target = root / rel
        if target.is_symlink() or target.parent.is_symlink():
            raise ImportValidationError(f"Symlink destination is forbidden: {rel}")
        digest = hashlib.sha256(data).hexdigest()
        dimensions = checked_png(data, (BATCH1 if category == "concepts" else BATCH2)[filename])
        if target.exists() and (not target.is_file() or target.read_bytes() != data):
            raise ImportValidationError(f"Refusing to overwrite different file: {rel}")
        planned.append({
            "path": rel, "source_name": filename,
            "sha256": digest, "size_bytes": len(data),
            "width": dimensions[0], "height": dimensions[1],
            "source_batch": "batch1" if category == "concepts" else "batch2",
        })
    manifest_path = root / "asset-checksums.json"
    if manifest_path.is_symlink():
        raise ImportValidationError("Manifest cannot be a symbolic link")
    previous = {}
    if manifest_path.exists():
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        if document.get("schema_version") != 1 or not isinstance(document.get("items"), list):
            raise ImportValidationError("Unexpected existing manifest schema")
        for item in document["items"]:
            rel = item.get("path")
            if not isinstance(rel, str) or rel in previous or rel not in {
                f"concepts/{name}" for name in BATCH1
            } | {f"screenshots/{name}" for name in BATCH2}:
                raise ImportValidationError("Unknown or duplicate manifest asset path")
            current = root / rel
            if current.is_symlink() or not current.is_file():
                raise ImportValidationError(f"Manifest source file missing: {rel}")
            if hashlib.sha256(current.read_bytes()).hexdigest() != item.get("sha256"):
                raise ImportValidationError(f"Existing asset digest mismatch: {rel}")
            previous[rel] = item
    for item in planned:
        original = previous.get(item["path"])
        if original is not None and original != item:
            raise ImportValidationError(
                f"Refusing to modify existing manifest entry: {item['path']}"
            )
        previous[item["path"]] = item
    if not write:
        return planned
    created: list[Path] = []
    staged_manifest: Path | None = None
    try:
        for filename, (data, category) in sorted(inputs.items()):
            target = root / category / filename
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                created.append(target)
                output.write(data)
        manifest = {
            "schema_version": 1,
            "design": "Sunset Studio (Colour Option F)",
            "items": [previous[name] for name in sorted(previous)],
        }
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=root, prefix=".asset-checksums-",
            suffix=".tmp", delete=False,
        ) as output:
            staged_manifest = Path(output.name)
            json.dump(manifest, output, indent=2, ensure_ascii=True)
            output.write("\n")
        os.replace(staged_manifest, manifest_path)
    except Exception:
        if staged_manifest is not None:
            staged_manifest.unlink(missing_ok=True)
        for target in reversed(created):
            target.unlink(missing_ok=True)
        raise
    return planned


def main(argv: list[str] | None = None) -> int:
    """Parse local paths and explicitly require --write before changing files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch2-zip", type=Path, help="Original approved Batch 2 review ZIP"
    )
    parser.add_argument(
        "--batch1-dir", type=Path, help="Folder with seven original Batch 1 PNGs"
    )
    parser.add_argument(
        "--write", action="store_true", help="Write verified files (default: dry-run)"
    )
    args = parser.parse_args(argv)
    if not args.batch2_zip and not args.batch1_dir:
        parser.error("Provide --batch2-zip and/or --batch1-dir")
    try:
        inputs = {}
        if args.batch2_zip:
            inputs.update(inspect_batch2(args.batch2_zip))
        if args.batch1_dir:
            inputs.update(inspect_batch1(args.batch1_dir))
        planned = import_assets(inputs, root=DESIGN_ROOT, write=args.write)
    except (ImportValidationError, OSError, ValueError) as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    label = "WRITTEN" if args.write else "DRY-RUN"
    print(f"{label}: {len(planned)} original PNGs validated; no Git operations performed")
    for item in planned:
        print(f"  {item['path']}  sha256={item['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
