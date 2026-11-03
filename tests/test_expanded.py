import tempfile
import unittest
from pathlib import Path
from aureon.db import initialize
from aureon.workflows import initialize_workspace,request_approval,decide_approval,create_record
from aureon.research import assess_opportunity,save_opportunity
from aureon.suppliers import add_supplier,add_quote,compare_supplier_quotes
from aureon.operations import create_order,request_supplier_order_approval,record_supplier_submission,update_tracking
from aureon.analytics import campaign_metrics,record_campaign_metrics
from aureon.scheduler import initialize_scheduler,schedule_job,enqueue_due
from aureon.jobs import list_jobs
from aureon.worker import process_job

class ExpandedCommerceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"a.sqlite3"
  initialize(self.db);initialize_workspace(self.db);initialize_scheduler(self.db)
 def tearDown(self): self.tmp.cleanup()
 def evidence(self):
  return [{"source_url":"https://example.com/report","source":"analyst","collected_at":"2026-11-03T10:00:00+00:00","observation":"Search interest rising"}]
 def signals(self):
  return {"demand":80,"trend":75,"margin":70,"competition":60,"shipping":90,"confidence":85}
 def test_opportunity_requires_evidence_and_scores(self):
  a=assess_opportunity("Desk mat",self.evidence(),self.signals())
  self.assertEqual(a["score"]["score"],74.25)
  saved=save_opportunity(self.db,"Desk mat",self.evidence(),self.signals())
  self.assertEqual(saved["record"]["kind"],"opportunity")
 def test_supplier_quotes_compare_same_destination_currency(self):
  s=add_supplier(self.db,"Supplier A","manual","desk mat","https://example.com")
  add_quote(self.db,s["id"],{"product_cost":8,"shipping_cost":3,"currency":"USD","destination":"US","quoted_at":"2026-11-03T10:00:00+00:00"})
  result=compare_supplier_quotes(self.db,"desk mat","US","USD")
  self.assertEqual(result["best_quote"]["landed_cost"],11)
  self.assertEqual(result["best_quote"]["status"],"unverified")
 def test_order_requires_approval_before_submission(self):
  order=create_order(self.db,"Desk mat",2,8,"USD")
  with self.assertRaises(ValueError): record_supplier_submission(self.db,order["id"],999,"PO-1")
  _,approval=request_supplier_order_approval(self.db,order["id"])
  decide_approval(self.db,approval["id"],"approved")
  submitted=record_supplier_submission(self.db,order["id"],approval["id"],"PO-1")
  self.assertEqual(submitted["data"]["supplier_order_status"],"submitted")
  shipped=update_tracking(self.db,order["id"],"TRACK-1","shipped")
  self.assertEqual(shipped["data"]["fulfillment_status"],"shipped")
 def test_campaign_metrics_are_computed_and_stored(self):
  campaign=create_record(self.db,"campaign","Test campaign",{},"draft")
  m=record_campaign_metrics(self.db,campaign["id"],{"impressions":1000,"clicks":50,"orders":5,"spend":20,"revenue":100})
  self.assertEqual(m["click_through_rate"],0.05)
  self.assertEqual(m["return_on_ad_spend"],5)
  self.assertIn("not profit",m["warning"])
 def test_scheduler_enqueues_due_jobs_idempotently(self):
  schedule_job(self.db,"design.brief",{"niche":"space","audience":"students","product_type":"tee","style":"minimal","concept":"planets"},"2026-11-03T10:00:00+00:00","schedule-1")
  result=enqueue_due(self.db,"2026-11-03T11:00:00+00:00")
  self.assertEqual(len(result),1)
  self.assertEqual(len(list_jobs(self.db)),1)
  self.assertEqual(enqueue_due(self.db,"2026-11-03T11:00:00+00:00"),[])
 def test_worker_assesses_opportunity(self):
  result=process_job({"kind":"opportunity.assess","payload":{"title":"Desk mat","evidence":self.evidence(),"signals":self.signals()}})
  self.assertEqual(result["result"]["score"]["score"],74.25)
 def test_campaign_metric_validation(self):
  with self.assertRaises(ValueError): campaign_metrics({"impressions":2,"clicks":3,"orders":0,"spend":0,"revenue":0})

if __name__=="__main__": unittest.main()
