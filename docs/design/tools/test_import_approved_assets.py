"""Regression tests for the approved-design importer trust and immutability gates."""

from __future__ import annotations

import json
import struct
import unittest
import zlib
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

import import_approved_assets as importer


def png_chunk(kind: bytes, content: bytes) -> bytes:
    """Create a checksummed PNG chunk for compact synthetic test fixtures."""
    payload = kind + content
    return struct.pack(">I", len(content)) + payload + struct.pack(">I", zlib.crc32(payload))


def image_of_size(target_size: int) -> bytes:
    """Generate an internally valid 1x1 PNG with an exact synthetic byte count."""
    ihdr = png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    idat = png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff"))
    iend = png_chunk(b"IEND", b"")
    base = importer.PNG_MAGIC + ihdr + idat + iend
    extra = target_size - len(base)
    if extra < 13:
        raise ValueError("Synthetic fixture too small")
    return (
        importer.PNG_MAGIC
        + ihdr
        + png_chunk(b"tEXt", b"K\x00" + b"x" * (extra - 14))
        + idat
        + iend
    )


class ImportApprovedAssetsTests(unittest.TestCase):
    """Exercise exact-name, byte integrity, archive and write protection rules."""

    def setUp(self) -> None:
        """Use temporary synthetic-sized files, never copying approved user PNGs."""
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.design = self.root / "docs" / "design"
        self.batch1 = {name: 200 + n for n, name in enumerate(importer.BATCH1, 1)}
        self.batch2 = {name: 220 + n for n, name in enumerate(importer.BATCH2, 1)}
        patches = ExitStack()
        patches.enter_context(patch.object(importer, "BATCH1", self.batch1))
        patches.enter_context(patch.object(importer, "BATCH2", self.batch2))
        self.addCleanup(patches.close)

    def make_archive(
        self, *, remove: str | None = None, extra: dict[str, bytes] | None = None
    ) -> Path:
        """Create a ZIP where approved PNGs are nested under a harmless folder."""
        archive = self.root / "batch2.zip"
        with ZipFile(archive, "w") as zipped:
            for name, size in self.batch2.items():
                if name != remove:
                    zipped.writestr(f"pack/{name}", image_of_size(size))
            zipped.writestr("pack/08-producer-review-queue.html", "<html>concept only</html>")
            for name, data in (extra or {}).items():
                zipped.writestr(name, data)
        return archive

    def make_batch1(self) -> Path:
        """Create a folder containing only the seven exact approved-style filenames."""
        directory = self.root / "batch1"
        directory.mkdir()
        for name, size in self.batch1.items():
            (directory / name).write_bytes(image_of_size(size))
        return directory

    def test_batch2_dry_run_then_write_records_exact_hashes(self) -> None:
        """Default validation makes no writes; explicit write preserves every byte."""
        sources = importer.inspect_batch2(self.make_archive())
        self.assertEqual(len(sources), 14)
        plans = importer.import_assets(sources, root=self.design, write=False)
        self.assertEqual(len(plans), 14)
        self.assertFalse(self.design.exists())
        importer.import_assets(sources, root=self.design, write=True)
        manifest = json.loads((self.design / "asset-checksums.json").read_text())
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(len(manifest["items"]), 14)
        for name, (data, category) in sources.items():
            self.assertEqual((self.design / category / name).read_bytes(), data)

    def test_batch1_can_merge_into_existing_manifest_without_overwriting(self) -> None:
        """Seven separate concepts augment an existing screenshot-only archive."""
        screenshots = importer.inspect_batch2(self.make_archive())
        importer.import_assets(screenshots, root=self.design, write=True)
        concepts = importer.inspect_batch1(self.make_batch1())
        importer.import_assets(concepts, root=self.design, write=True)
        manifest = json.loads((self.design / "asset-checksums.json").read_text())
        self.assertEqual(len(manifest["items"]), 21)
        # Repeating the same import is idempotent.
        importer.import_assets(concepts, root=self.design, write=True)
        self.assertEqual(
            len(json.loads((self.design / "asset-checksums.json").read_text())["items"]),
            21,
        )

    def test_missing_batch2_asset_fails_closed(self) -> None:
        """A partial ZIP cannot be represented as the complete approved Batch 2."""
        with self.assertRaisesRegex(importer.ImportValidationError, "Missing Batch 2"):
            importer.inspect_batch2(self.make_archive(remove=next(iter(self.batch2))))

    def test_unknown_png_rejected(self) -> None:
        """Unapproved or accidentally included PNGs may not enter design docs."""
        with self.assertRaisesRegex(importer.ImportValidationError, "Unrecognised PNG"):
            importer.inspect_batch2(
                self.make_archive(extra={"pack/unapproved.png": image_of_size(220)})
            )

    def test_zip_traversal_rejected(self) -> None:
        """A traversal member is rejected despite not being selected for import."""
        with self.assertRaisesRegex(importer.ImportValidationError, "Unsafe ZIP"):
            importer.inspect_batch2(self.make_archive(extra={"../bad.txt": b"malicious"}))

    def test_duplicate_filename_rejected(self) -> None:
        """Two files with the same basename cannot silently select a wrong source."""
        name = next(iter(self.batch2))
        with self.assertRaisesRegex(importer.ImportValidationError, "Duplicate PNG"):
            importer.inspect_batch2(
                self.make_archive(extra={f"other/{name}": image_of_size(self.batch2[name])})
            )

    def test_png_chunk_crc_rejected(self) -> None:
        """The exact length alone must not let a damaged PNG through."""
        image = bytearray(image_of_size(240))
        image[50] ^= 1
        with self.assertRaisesRegex(importer.ImportValidationError, "Invalid PNG CRC"):
            importer.checked_png(bytes(image), 240)

    def test_existing_different_file_blocks_all_writes(self) -> None:
        """A conflicting destination rejects the whole import before new writes."""
        sources = importer.inspect_batch2(self.make_archive())
        name = sorted(sources)[0]
        target = self.design / "screenshots" / name
        target.parent.mkdir(parents=True)
        target.write_bytes(b"do not replace")
        with self.assertRaisesRegex(importer.ImportValidationError, "Refusing to overwrite"):
            importer.import_assets(sources, root=self.design, write=True)
        self.assertEqual(target.read_bytes(), b"do not replace")
        self.assertEqual(list(target.parent.iterdir()), [target])

    def test_tampered_manifest_is_rejected(self) -> None:
        """An old image modified after import must not pass the next archive run."""
        sources = importer.inspect_batch2(self.make_archive())
        importer.import_assets(sources, root=self.design, write=True)
        filename = next(iter(sources))
        (self.design / "screenshots" / filename).write_bytes(b"tampered")
        with self.assertRaises(importer.ImportValidationError):
            importer.import_assets(
                importer.inspect_batch1(self.make_batch1()), root=self.design, write=True
            )


if __name__ == "__main__":
    unittest.main()
