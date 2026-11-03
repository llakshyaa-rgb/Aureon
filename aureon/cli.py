"""Aureon command-line entry point."""
import argparse
from . import __version__
from .config import Settings
from .db import connect,initialize
from .server import serve
from .features import all_features
from .workflows import initialize_workspace,list_records,finance_summary,list_approvals
from .worker import run_until_empty
from .scheduler import initialize_scheduler,enqueue_due

def main():
 p=argparse.ArgumentParser(prog="aureon");sub=p.add_subparsers(dest="command",required=True)
 sub.add_parser("init",help="initialize local SQLite storage")
 sub.add_parser("run",help="start the local dashboard and API")
 sub.add_parser("status",help="show local runtime status")
 sub.add_parser("features",help="list product scope and implementation status")
 sub.add_parser("workspace",help="show local commerce workspace records")
 w=sub.add_parser("work",help="process queued mock-mode jobs");w.add_argument("--max-jobs",type=int,default=100)
 t=sub.add_parser("tick",help="enqueue due scheduled jobs without executing them");t.add_argument("--now",default=None)
 args=p.parse_args()
 if args.command=="features":
  print("Aureon %s — product scope"%__version__)
  for d in all_features():
   print("\n%s [%s]"%(d["name"],d["status"]))
   for f in d["features"]: print("  - "+f)
  return
 s=Settings.from_env()
 if args.command=="init":
  initialize(s.db_path);initialize_workspace(s.db_path);initialize_scheduler(s.db_path)
  print("Initialized Aureon database:",s.db_path)
 elif args.command=="run": serve(s.host,s.port,s.db_path)
 elif args.command=="status":
  initialize(s.db_path);initialize_workspace(s.db_path);initialize_scheduler(s.db_path)
  with connect(s.db_path) as c: rows=c.execute("SELECT status,COUNT(*) n FROM jobs GROUP BY status").fetchall()
  print("Aureon %s | mode=%s"%(__version__,s.mode));print("Database:",s.db_path)
  print("Jobs:",", ".join("%s=%s"%(r["status"],r["n"]) for r in rows) or "none")
  print("Workspace records:",len(list_records(s.db_path)))
  print("Pending approvals:",sum(1 for a in list_approvals(s.db_path) if a["status"]=="pending"))
  print("Finance:",finance_summary(s.db_path))
 elif args.command=="work":
  initialize(s.db_path);initialize_workspace(s.db_path);outcomes=run_until_empty(s.db_path,args.max_jobs)
  print("Processed",len(outcomes),"jobs")
  for item in outcomes: print(item)
 elif args.command=="tick":
  initialize(s.db_path);initialize_scheduler(s.db_path);print("Enqueued due jobs:",enqueue_due(s.db_path,args.now))
 elif args.command=="workspace":
  initialize(s.db_path);initialize_workspace(s.db_path)
  for r in list_records(s.db_path): print("#%s %s [%s] %s"%(r["id"],r["kind"],r["status"],r["title"]))
if __name__=="__main__": main()
