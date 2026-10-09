"""``python -m marsad.api``: run the REST/SSE service and dashboard with uvicorn."""
from __future__ import annotations

import argparse


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m marsad.api", description="Marsad REST/SSE service + dashboard")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--log-level", default="info")
    a = ap.parse_args(argv)
    import uvicorn
    from .app import create_app
    uvicorn.run(create_app(), host=a.host, port=a.port, log_level=a.log_level,
                timeout_graceful_shutdown=2)   # SSE streams never end on their own
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
