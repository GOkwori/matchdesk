"""Check that documentation and source-identity gates detect actual mistakes."""

from pathlib import Path

from scripts.check_comments import inspect_python
from scripts.check_docs import markdown_errors
from scripts.collect_evidence import source_inventory


def test_missing_docstrings_are_reported(tmp_path: Path) -> None:
    """Missing documentation must fail with a location instead of passing silently."""
    file = tmp_path / "sample.py"
    file.write_text("def example():\n    return 1\n", encoding="utf-8")
    count, errors = inspect_python(file)
    assert count == 2
    assert len(errors) == 2


def test_documented_callable_is_accepted(tmp_path: Path) -> None:
    """A module and callable with useful explanations satisfy the presence gate."""
    file = tmp_path / "sample.py"
    file.write_text(
        '"""Convert a fixture for a boundary test."""\n'
        'def example():\n    """Return the expected fixture identity."""\n    return 1\n',
        encoding="utf-8",
    )
    assert inspect_python(file) == (2, [])


def test_broken_and_external_markdown_links(tmp_path: Path) -> None:
    """Local links must exist; external references do not trigger a network dependency."""
    file = tmp_path / "README.md"
    file.write_text("[missing](missing.md) [external](https://example.com)\n", encoding="utf-8")
    assert len(markdown_errors(file, tmp_path)) == 1
    (tmp_path / "missing.md").write_text("A valid local target.\n", encoding="utf-8")
    assert markdown_errors(file, tmp_path) == []


def test_manifest_excludes_secrets_and_generated_evidence(tmp_path: Path) -> None:
    """Evidence must identify source without copying secrets or hashing itself."""
    (tmp_path / "source.py").write_text('"""Source fixture."""\n', encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=not-a-real-credential\n", encoding="utf-8")
    evidence = tmp_path / "docs/evidence"
    evidence.mkdir(parents=True)
    (evidence / "result.json").write_text("{}", encoding="utf-8")
    assert list(source_inventory(tmp_path)) == ["source.py"]
