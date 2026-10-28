"""``python -m marsad.api``: run the REST/SSE service and dashboard with uvicorn."""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m marsad.api", description="Marsad REST/SSE service + dashboard")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--log-level", default="info")
    ap.add_argument(
        "--insecure",
        action="store_true",
        help="allow a non loopback bind without MARSAD_API_KEY (the acknowledge endpoint is then open to the network)",
    )
    a = ap.parse_args(argv)
    if not _is_loopback(a.host) and not os.environ.get("MARSAD_API_KEY") and not a.insecure:
        print(
            f"refusing to bind {a.host} without MARSAD_API_KEY: anyone who can reach the port could post samples or "
            "acknowledge a distrusted position. Set MARSAD_API_KEY, or pass --insecure on a closed network.",
            file=sys.stderr,
        )
        return 2
    import uvicorn

    from .app import create_app

    uvicorn.run(
        create_app(), host=a.host, port=a.port, log_level=a.log_level, timeout_graceful_shutdown=2
    )  # SSE streams never end on their own
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
