"""Aureon command-line entry point."""
import argparse
from . import __version__
from .config import Settings
from .db import connect, initialize
from .server import serve
from .features import all_features

def main():
    parser = argparse.ArgumentParser(prog="aureon")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="initialize local SQLite storage")
    sub.add_parser("run", help="start the local dashboard and API")
    sub.add_parser("status", help="show local runtime status")
    sub.add_parser("features", help="list the complete product scope and implementation status")
    args = parser.parse_args()
    if args.command == "features":
        print("Aureon %s — product scope" % __version__)
        for domain in all_features():
            print("\n%s [%s]" % (domain["name"], domain["status"]))
            for feature in domain["features"]:
                print("  - " + feature)
        return
    settings = Settings.from_env()
    if args.command == "init":
        initialize(settings.db_path)
        print("Initialized database:", settings.db_path)
    elif args.command == "run":
        serve(settings.host, settings.port, settings.db_path)
    elif args.command == "status":
        initialize(settings.db_path)
        with connect(settings.db_path) as conn:
            rows = conn.execute("SELECT status,COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
        print("Aureon %s | mode=%s" % (__version__, settings.mode))
        print("Database:", settings.db_path)
        print("Jobs:", ", ".join("%s=%s" % (r["status"], r["n"]) for r in rows) or "none")

if __name__ == "__main__":
    main()
