"""`python -m crafting_system.web [--host HOST] [--port PORT] [--workers N] [--db PATH]`: the website's service, one command (`docs/web.md`).

Each flag has an environment variable for a container: `CRAFTING_WEB_HOST` (default 127.0.0.1), `CRAFTING_WEB_PORT` (8000),
`CRAFTING_WEB_WORKERS` (1: plans run at once; each plan also uses the cores `CRAFTING_WORKERS` gives it) and `CRAFTING_WEB_DB` (the SQLite
file, default `<output folder>/web/site.sqlite3`). The game data, the prices and the planner's limits are the command's (`crafting.toml`).
"""

import argparse
import os
import sys

from crafting_system.config import load_config

from ._app import create_app
from ._service import Service
from ._store import SqliteStore
from ._world import load_world


def main(argv: list[str] | None = None) -> int:
    import uvicorn  # noqa: PLC0415  (the server is the `web` extra's; the app itself needs only Starlette)

    config = load_config()
    parser = argparse.ArgumentParser(prog="python -m crafting_system.web", description="The planner behind an HTTP API (docs/web.md).")
    parser.add_argument("--host", default=os.environ.get("CRAFTING_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CRAFTING_WEB_PORT", "8000")))
    parser.add_argument("--workers", type=int, default=int(os.environ.get("CRAFTING_WEB_WORKERS", "1")), help="plans run at once")
    parser.add_argument("--db", default=os.environ.get("CRAFTING_WEB_DB") or str(config.output_dir / "web" / "site.sqlite3"), help="the SQLite file of the store")
    args = parser.parse_args(argv)
    service = Service(SqliteStore(args.db), load_world, game="poe1", workers=args.workers)
    uvicorn.run(create_app({"poe1": service}), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
