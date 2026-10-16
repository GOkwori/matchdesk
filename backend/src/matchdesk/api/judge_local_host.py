"""Explicit local-only judge host; the exported foundation API is unchanged.

Run using the reviewed locked Python environment. Never bind on all network
interfaces, trust proxy-forwarded addresses or enable an access-token log.
"""

from __future__ import annotations

import uvicorn

from matchdesk.api.judge_local_routes import create_judge_local_app

app = create_judge_local_app()


def main() -> None:
    """Serve one disposable in-memory process bound exclusively to IPv4 loopback."""
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        proxy_headers=False,
        forwarded_allow_ips="",
        server_header=False,
        access_log=False,
        workers=1,
    )


if __name__ == "__main__":
    main()
