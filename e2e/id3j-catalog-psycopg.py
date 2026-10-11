"""Run the ID3J SQL privilege probe against a dedicated disposable CI database."""

import os

import psycopg

from matchdesk.domain.id3h_release_approval import ReleaseDenied
from matchdesk.domain.id3j_postgres_catalog import inspect_disposable_catalog


def main() -> None:
    """Require the exact disposable role and verify read-only catalog facts."""
    if os.environ.get("CI") != "true" or not os.environ.get("PGPASSWORD"):
        raise ReleaseDenied("ID3J disposable catalog preflight denied")
    with psycopg.connect(
        "host=postgres dbname=matchdesk_id3j_ci user=matchdesk_id3j_reader_ci "
        "sslmode=prefer"
    ) as conn:
        receipt = inspect_disposable_catalog(conn)
    assert receipt.database_writes_authorized is False
    assert receipt.execution_authorized is False
    print("MATCHDESK_ID3J_CATALOG_READ_ONLY_PASS")


if __name__ == "__main__":
    main()
