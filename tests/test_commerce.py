import tempfile
import unittest
from pathlib import Path
from aureon.db import initialize
from aureon.workflows import initialize_workspace
from aureon.commerce import (build_design_brief,generate_listing_draft,draft_marketing_content,
 triage_support_ticket,create_support_ticket,summarize_performance)

class CommerceDraftTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/"a.sqlite3"
  initialize(self.db); initialize_workspace(self.db)
 def tearDown(self): self.tmp.cleanup()
 def test_design_brief_flags_rights_review(self):
  b=build_design_brief("space","students","tee","minimal line art","orbiting planets")
  self.assertTrue(b["trademark_review_required"]); self.assertIn("original",b["prompt"])
 def test_listing_is_draft_and_has_review_checks(self):
  x=generate_listing_draft({"title":"Planet Desk Mat","features":"Smooth surface."},"students",["desk mat","space"])
  self.assertEqual(x["status"],"draft"); self.assertTrue(x["review_required"])
 def test_marketing_rejects_unknown_channel(self):
  with self.assertRaises(ValueError): draft_marketing_content("Mug","readers","spam-site","Nice","Buy")
 def test_support_escalates_legal_and_injury(self):
  self.assertEqual(triage_support_ticket("Help","This caused an injury")["priority"],"urgent")
  self.assertEqual(triage_support_ticket("Order","Please refund me")["category"],"refund_or_cancellation")
 def test_support_record_created(self):
  t=create_support_ticket(self.db,"Tracking","Where is my order?")
  self.assertEqual(t["kind"],"support_ticket")
 def test_analytics_counts_records(self):
  self.assertEqual(summarize_performance({},[{"kind":"product"},{"kind":"product"}])["record_counts"]["product"],2)

if __name__=="__main__": unittest.main()
