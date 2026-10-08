"""Start the actual local HTTP server and smoke-test its foundation boundary.

The process is always stopped, including on failed validation or timeout. This
checks local networking, not a Docker image or an Azure deployment.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Validate liveness, deliberate non-readiness and real event-validation HTTP."""
    # Select an unused loopback port without opening a publicly reachable listener.
    with socket.socket() as allocation:
        allocation.bind(("127.0.0.1", 0))
        port = allocation.getsockname()[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    address = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile(mode="w+") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "matchdesk.api.app:app", "--host", "127.0.0.1",
             "--port", str(port), "--no-access-log"], cwd=ROOT, env=environment,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(40):
                try:
                    with urllib.request.urlopen(address + "/api/health", timeout=1) as response:
                        health = json.load(response)
                    break
                except (OSError, urllib.error.URLError):
                    if process.poll() is not None:
                        raise RuntimeError("The local HTTP server exited before becoming live")
                    time.sleep(0.1)
            else:
                raise TimeoutError("Local HTTP server did not start in the bounded interval")
            assert health["status"] == "alive"
            assert health["model_mode"] == "not_connected"
            try:
                urllib.request.urlopen(address + "/api/ready", timeout=2)
            except urllib.error.HTTPError as error:
                assert error.code == 503
            else:
                raise AssertionError("The incomplete product must not report readiness")
            payload = {"event_id": "smoke-period", "match_id": "smoke-match", "sequence": 0,
                       "period": 1, "match_clock_ms": 0, "type": "period_start", "synthetic": True}
            request = urllib.request.Request(
                address + "/api/contracts/event/validate", data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                validated = json.load(response)
            assert validated["structurally_valid"] is True
            assert validated["evidence_verified"] is False
            print(json.dumps({"health_http": 200, "readiness_http": 503, "validation_http": 200,
                              "scope": "native_loopback_http", "models": "not_connected"}, indent=2))
            return 0
        except Exception:
            # Print only local service diagnostics; no credentials are supplied to this smoke test.
            log.seek(0)
            print(log.read(), file=sys.stderr)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
