import tempfile,unittest
from pathlib import Path
from aureon.db import initialize
from aureon.workflows import initialize_workspace,request_approval,decide_approval,create_record,transition_record,add_finance_entry
from aureon.research import assess_opportunity,save_opportunity
from aureon.suppliers import add_supplier,add_quote,compare_supplier_quotes
from aureon.operations import create_order,request_supplier_order_approval,record_supplier_submission,update_tracking
from aureon.analytics import campaign_metrics,record_campaign_metrics
from aureon.scheduler import initialize_scheduler,schedule_job,enqueue_due
from aureon.jobs import list_jobs,enqueue
from aureon.worker import process_job,run_once

class ExpandedCommerceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"a.sqlite3"
  initialize(self.db);initialize_workspace(self.db);initialize_scheduler(self.db)
 def tearDown(self):self.tmp.cleanup()
 def evidence(self):
  return [{"source_url":"https://example.com/report","source":"analyst","collected_at":"2026-11-03T10:00:00+00:00","observation":"Search interest rising"}]
 def signals(self):return {"demand":80,"trend":75,"margin":70,"competition":60,"shipping":90,"confidence":85}
 def test_opportunity_requires_unique_traceable_evidence_and_scores(self):
  a=assess_opportunity("Desk mat",self.evidence(),self.signals())
  self.assertEqual(a["score"]["score"],74.25)
  self.assertEqual(save_opportunity(self.db,"Desk mat",self.evidence(),self.signals())["record"]["kind"],"opportunity")
  with self.assertRaises(ValueError):assess_opportunity("Bad",[],self.signals())
  with self.assertRaises(ValueError):assess_opportunity("Bad",[{"source_url":"file:///etc/passwd","collected_at":"2026-11-03T10:00:00Z"}],self.signals())
 def test_supplier_quotes_compare_only_same_destination_currency(self):
  s=add_supplier(self.db,"Supplier A","manual","desk mat","https://example.com")
  add_quote(self.db,s["id"],{"product_cost":8,"shipping_cost":3,"currency":"USD","destination":"US","quoted_at":"2026-11-03T10:00:00+00:00"})
  add_quote(self.db,s["id"],{"product_cost":1,"shipping_cost":1,"currency":"INR","destination":"IN","quoted_at":"2026-11-03T10:00:00+00:00"})
  r=compare_supplier_quotes(self.db,"desk mat","US","USD")
  self.assertEqual(r["best_quote"]["landed_cost"],11);self.assertEqual(len(r["quotes"]),1)
  with self.assertRaises(ValueError):add_quote(self.db,s["id"],{"product_cost":float("nan"),"shipping_cost":0,"currency":"USD","destination":"US","quoted_at":"2026-11-03T10:00:00Z"})
 def test_order_approval_is_matching_single_use_and_amount_bound(self):
  order=create_order(self.db,"Desk mat",2,8,"USD")
  with self.assertRaises(ValueError):record_supplier_submission(self.db,order["id"],999,"PO-1")
  _,approval=request_supplier_order_approval(self.db,order["id"])
  with self.assertRaises(ValueError):request_supplier_order_approval(self.db,order["id"])
  decide_approval(self.db,approval["id"],"approved")
  submitted=record_supplier_submission(self.db,order["id"],approval["id"],"PO-1")
  self.assertEqual(submitted["data"]["supplier_order_status"],"submitted")
  with self.assertRaises(ValueError):record_supplier_submission(self.db,order["id"],approval["id"],"PO-2")
  shipped=update_tracking(self.db,order["id"],"TRACK-1","in_production")
  shipped=update_tracking(self.db,order["id"],"TRACK-1","shipped")
  self.assertEqual(shipped["data"]["fulfillment_status"],"shipped")
  with self.assertRaises(ValueError):update_tracking(self.db,order["id"],"TRACK-1","in_production")
 def test_campaign_metrics_and_currency_are_persisted(self):
  c=create_record(self.db,"campaign","Test campaign",{},"draft")
  m=record_campaign_metrics(self.db,c["id"],{"impressions":1000,"clicks":50,"orders":5,"spend":20,"revenue":100,"currency":"USD"})
  self.assertEqual(m["click_through_rate"],0.05);self.assertEqual(m["return_on_ad_spend"],5)
  self.assertIn("not profit",m["warning"])
  with self.assertRaises(ValueError):record_campaign_metrics(self.db,c["id"],{"impressions":100,"clicks":1,"orders":1,"spend":1,"revenue":2,"currency":"INR"})
 def test_scheduler_idempotency_and_atomic_due_enqueue(self):
  p={"niche":"space","audience":"students","product_type":"tee","style":"minimal","concept":"planets"}
  schedule_job(self.db,"design.brief",p,"2026-11-03T10:00:00+00:00","schedule-1")
  with self.assertRaises(ValueError):schedule_job(self.db,"design.brief",{"different":True},"2026-11-03T10:00:00+00:00","schedule-1")
  r=enqueue_due(self.db,"2026-11-03T11:00:00+00:00");self.assertEqual(len(r),1)
  self.assertEqual(len(list_jobs(self.db)),1);self.assertEqual(enqueue_due(self.db,"2026-11-03T11:00:00+00:00"),[])
 def test_worker_persists_design_and_opportunity_records(self):
  enqueue(self.db,"design.brief",{"niche":"space","audience":"students","product_type":"tee","style":"minimal","concept":"planets"})
  r=run_once(self.db);self.assertEqual(r["status"],"succeeded")
  self.assertEqual(r["result"]["result"]["record"]["kind"],"design")
  result=process_job({"kind":"opportunity.assess","payload":{"title":"Desk mat","evidence":self.evidence(),"signals":self.signals()}},self.db)
  self.assertEqual(result["result"]["result"]["assessment"]["score"],74.25)
 def test_campaign_metric_validation_and_state_transition(self):
  with self.assertRaises(ValueError):campaign_metrics({"impressions":2,"clicks":3,"orders":0,"spend":0,"revenue":0})
  c=create_record(self.db,"campaign","Campaign",{},"draft")
  with self.assertRaises(ValueError):transition_record(self.db,c["id"],"running")
  with self.assertRaises(ValueError):add_finance_entry(self.db,"revenue",float("inf"),"USD","Bad")
if __name__=="__main__":unittest.main()
