"""Aureon command-line entry point."""
import argparse
from . import __version__
from .config import Settings
from .db import connect, initialize
from .server import serve
from .features import all_features
from .workflows import initialize_workspace, list_records, finance_summary, list_approvals

def main():
    parser=argparse.ArgumentParser(prog="aureon")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("init",help="initialize local SQLite storage")
    sub.add_parser("run",help="start the local dashboard and API")
    sub.add_parser("status",help="show local runtime status")
    sub.add_parser("features",help="list product scope and implementation status")
    sub.add_parser("workspace",help="show local commerce workspace records")
    args=parser.parse_args()
    if args.command=="features":
        print("Aureon %s — product scope"%__version__)
        for d in all_features():
            print("\n%s [%s]"%(d["name"],d["status"]))
            for f in d["features"]: print("  - "+f)
        return
    settings=Settings.from_env()
    if args.command=="init":
        initialize(settings.db_path); initialize_workspace(settings.db_path)
        print("Initialized Aureon database:",settings.db_path)
    elif args.command=="run": serve(settings.host,settings.port,settings.db_path)
    elif args.command=="status":
        initialize(settings.db_path); initialize_workspace(settings.db_path)
        with connect(settings.db_path) as conn:
            rows=conn.execute("SELECT status,COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
        print("Aureon %s | mode=%s"%(__version__,settings.mode))
        print("Database:",settings.db_path)
        print("Jobs:",", ".join("%s=%s"%(r["status"],r["n"]) for r in rows) or "none")
        print("Workspace records:",len(list_records(settings.db_path)))
        print("Pending approvals:",sum(1 for a in list_approvals(settings.db_path) if a["status"]=="pending"))
        print("Finance:",finance_summary(settings.db_path))
    elif args.command=="workspace":
        initialize(settings.db_path); initialize_workspace(settings.db_path)
        for r in list_records(settings.db_path): print("#%s %s [%s] %s"%(r["id"],r["kind"],r["status"],r["title"]))

if __name__=="__main__": main()
