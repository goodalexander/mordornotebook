"""Local smoke check for Mordor Notebook MVP contracts."""

from __future__ import annotations

import json

from mordornotebook import attach
from mordornotebook.http_client import request_json


def main() -> int:
    session = attach(repo=".", goal="smoke")
    try:
        try:
            import pandas as pd

            obj = pd.DataFrame({"ticker": ["AAPL", "MSFT"], "pnl": [1.2, -0.4]})
        except Exception:
            obj = {"ticker": ["AAPL", "MSFT"], "pnl": [1.2, -0.4]}
        session.register("panel", obj)
        health = request_json(str(session.bridge_url), "GET", "/health")
        memory = request_json(str(session.bridge_url), "GET", "/memory")
        context = request_json(str(session.bridge_url), "GET", "/context")
        print(json.dumps({"health": health["ok"], "memory_count": len(memory["objects"]), "context_keys": sorted(context)}, indent=2))
        return 0
    finally:
        session.stop_bridge()


if __name__ == "__main__":
    raise SystemExit(main())
