import tempfile
import unittest
from pathlib import Path
from aureon.db import initialize
from aureon.workflows import (initialize_workspace,create_record,list_records,transition_record,
 request_approval,decide_approval,add_finance_entry,finance_summary)

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.db=Path(self.temp.name)/"a.sqlite3"
        initialize(self.db); initialize_workspace(self.db)
    def tearDown(self): self.temp.cleanup()
    def test_opportunity_requires_traceable_evidence(self):
        with self.assertRaises(ValueError):
            create_record(self.db,"opportunity","Desk mat idea",{"evidence":[{"source_url":"https://example.com"}]})
        item=create_record(self.db,"opportunity","Desk mat idea",{"evidence":[{"source_url":"https://example.com","collected_at":"2026-11-03T00:00:00Z"}]})
        self.assertEqual(item["kind"],"opportunity")
    def test_product_and_status_transition(self):
        item=create_record(self.db,"product","Minimal desk mat",{"selling_price":29.99})
        updated=transition_record(self.db,item["id"],"approved")
        self.assertEqual(updated["status"],"approved")
        self.assertEqual(len(list_records(self.db,"product")),1)
    def test_invalid_price_rejected(self):
        with self.assertRaises(ValueError): create_record(self.db,"product","Bad item",{"selling_price":-1})
    def test_approval_is_single_use(self):
        a=request_approval(self.db,"place_supplier_order","order","42","Supplier order",12.5,"USD")
        self.assertEqual(decide_approval(self.db,a["id"],"approved")["status"],"approved")
        with self.assertRaises(ValueError): decide_approval(self.db,a["id"],"approved")
    def test_finance_separates_actual_and_estimates(self):
        add_finance_entry(self.db,"revenue",100,"USD","Order payout",actual=True)
        add_finance_entry(self.db,"supplier_cost",30,"USD","Production estimate")
        summary=finance_summary(self.db)["USD"]
        self.assertEqual(summary["actual_net"],100)
        self.assertEqual(summary["estimated_net"],-30)
    def test_finance_rejects_negative_amount(self):
        with self.assertRaises(ValueError): add_finance_entry(self.db,"revenue",-10,"USD","bad")

if __name__=="__main__": unittest.main()
