import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from aureon.db import initialize
from aureon.jobs import enqueue,list_jobs
from aureon.worker import run_once,run_until_empty

class WorkerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/"a.sqlite3"; initialize(self.db)
 def tearDown(self): self.tmp.cleanup()
 def test_processes_design_brief(self):
  enqueue(self.db,"design.brief",{"niche":"space","audience":"students","product_type":"tee","style":"minimal","concept":"planets"})
  result=run_once(self.db)
  self.assertEqual(result["status"],"succeeded")
  self.assertEqual(list_jobs(self.db)[0]["result"]["mode"],"mock")
 def test_transient_runtime_error_is_requeued(self):
  enqueue(self.db,"trends.collect",{"geo":"IN","limit":1})
  with patch("aureon.worker.collect_trends",side_effect=RuntimeError("temporary provider outage")):
   result=run_once(self.db)
  self.assertEqual(result["status"],"retrying")
  self.assertEqual(list_jobs(self.db)[0]["status"],"queued")
  self.assertEqual(list_jobs(self.db)[0]["attempts"],1)
 def test_unknown_job_fails_without_loop(self):
  enqueue(self.db,"external.purchase",{})
  result=run_once(self.db)
  self.assertEqual(result["status"],"failed")
  self.assertEqual(list_jobs(self.db)[0]["status"],"failed")
 def test_run_until_empty(self):
  enqueue(self.db,"support.triage",{"subject":"Question","message":"Where is my order?"})
  self.assertEqual(len(run_until_empty(self.db)),1)

if __name__=="__main__": unittest.main()
