import tempfile,unittest
from pathlib import Path
from aureon.db import initialize
from aureon.workflows import initialize_workspace,decide_approval
from aureon.support import open_ticket,draft_response,support_queue,add_internal_note
from aureon.finance import reconcile,cashflow_projection
from aureon.marketing import create_campaign,request_campaign_approval,campaign_overview
from aureon.agents import plan_run,submit_plan,runtime_status
from aureon.command_center import dashboard_snapshot,interpret_command
from aureon.jobs import list_jobs
class LastSixTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"a.sqlite3";initialize(self.db);initialize_workspace(self.db)
 def tearDown(self):self.tmp.cleanup()
 def test_support_escalates_and_never_sends(self):
  t=open_ticket(self.db,"Unsafe product","I was injured using this item")
  self.assertEqual(t["status"],"escalated")
  d=draft_response(self.db,t["id"],"We are escalating this to our team.")
  self.assertFalse(d["sent"]);add_internal_note(self.db,t["id"],"Check incident")
  self.assertEqual(support_queue(self.db)["urgent_count"],1)
 def test_finance_reconciliation_and_forecast(self):
  r=reconcile(self.db,"USD",100,100);self.assertTrue(r["reconciled"])
  f=cashflow_projection(self.db,100,30,50,20,"USD");self.assertEqual(f["projected_closing_cash"],130)
  with self.assertRaises(ValueError):cashflow_projection(self.db,100,0,-1,2)
 def test_campaign_draft_requires_approval_and_does_not_publish(self):
  c=create_campaign(self.db,"Launch","Desk Mat","Students","instagram","Durable finish","See details",25,"USD")
  self.assertEqual(c["data"]["publication_status"],"draft_only")
  a=request_campaign_approval(self.db,c["id"],"spend_on_ads")
  self.assertEqual(a["status"],"pending");self.assertEqual(campaign_overview(self.db)[0]["spend_status"],"not_authorized")
 def test_agent_plan_is_allowlisted_and_idempotent(self):
  tasks=[{"kind":"support.triage","payload":{"subject":"Shipping","message":"Where is my order?"}}]
  self.assertEqual(len(plan_run("Support",tasks)["tasks"]),1)
  first=submit_plan(self.db,"Support",tasks,"plan-1")
  second=submit_plan(self.db,"Support",tasks,"plan-1")
  self.assertEqual(first["run_id"],second["run_id"]);self.assertTrue(second["duplicate"])
  self.assertEqual(len(list_jobs(self.db)),1)
  with self.assertRaises(ValueError):plan_run("Bad",[{"kind":"shell.exec","payload":{}}])
 def test_command_center_is_read_only_and_safe(self):
  snap=dashboard_snapshot(self.db);self.assertEqual(snap["mode"],"mock")
  self.assertFalse(snap["safety"]["publishing_enabled"])
  self.assertFalse(interpret_command("run arbitrary python")["recognized"])
  self.assertFalse(interpret_command("draft marketing copy for a mug")["submitted"])
if __name__=="__main__":unittest.main()
