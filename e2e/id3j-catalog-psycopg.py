"""Run the ID3J SQL privilege probe against a dedicated disposable CI database."""

import os

import psycopg

from matchdesk.domain.id3h_release_approval import ReleaseDenied
from matchdesk.domain.id3j_postgres_catalog import _CATALOG_QUERY, inspect_disposable_catalog



def _diagnose_disposable_denial(connection: psycopg.Connection) -> None:
    """Report only synthetic role capability bits, never secrets or claims.

    These diagnostics are restricted to the fixed, disposable CI role. The
    fail-closed inspector itself remains unchanged. Nothing here can permit
    a release or convert a failed check into a success.
    """
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(_CATALOG_QUERY)
                row = cursor.fetchone()
        if not isinstance(row, tuple):
            print("MATCHDESK_ID3J_CI_DIAG missing_catalog_row")
            return
        print(
            "MATCHDESK_ID3J_CI_DIAG "
            f"fields={len(row)} "
            f"database_match={row[0] == 'matchdesk_id3j_ci'} "
            f"role_match={row[1] == 'matchdesk_id3j_reader_ci'} "
            f"session_match={row[1] == row[2]} "
            f"true_capability_indices={[i for i, value in enumerate(row) if i >= 3 and value is True]} "
            f"other_types={[i for i, value in enumerate(row) if i >= 3 and type(value) is not bool]}",
            flush=True,
        )
    except Exception as exc:
        print(
            "MATCHDESK_ID3J_CI_DIAG query_error "
            f"class={type(exc).__name__} "
            f"sqlstate={getattr(exc, 'sqlstate', None)}",
            flush=True,
        )

def main() -> None:
    """Require the exact disposable role and verify read-only catalog facts."""
    if os.environ.get("CI") != "true" or not os.environ.get("PGPASSWORD"):
        raise ReleaseDenied("ID3J disposable catalog preflight denied")
    with psycopg.connect(
        "host=postgres dbname=matchdesk_id3j_ci user=matchdesk_id3j_reader_ci "
        "sslmode=prefer"
    ) as conn:
        try:
            receipt = inspect_disposable_catalog(conn)
        except ReleaseDenied:
            _diagnose_disposable_denial(conn)
            raise
    assert receipt.database_writes_authorized is False
    assert receipt.execution_authorized is False
    print("MATCHDESK_ID3J_CATALOG_READ_ONLY_PASS")


if __name__ == "__main__":
    main()
