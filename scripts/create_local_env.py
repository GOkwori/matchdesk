"""Create local-only database credentials without displaying or overwriting secrets."""
from pathlib import Path
import os
import secrets


def main() -> int:
    """Write an owner-readable ignored .env; existing configuration requires review."""
    destination = Path(__file__).resolve().parents[1] / ".env"
    # Exclusive creation avoids silently replacing credentials for an existing database.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n")
    print("Created ignored local configuration; secret values were not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
