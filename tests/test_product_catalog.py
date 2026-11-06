import tempfile,unittest
from pathlib import Path
from aureon.db import initialize
from aureon.workflows import initialize_workspace,create_record
from aureon.product_catalog import list_products,update_product

class ProductCatalogTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"a.sqlite3"
  initialize(self.db);initialize_workspace(self.db)
  self.product=create_record(self.db,"product","Desk mat",{"selling_price":499,"currency":"INR"})
 def tearDown(self): self.tmp.cleanup()
 def test_search_and_filter(self):
  create_record(self.db,"product","Travel mug",{"selling_price":299})
  self.assertEqual([x["title"] for x in list_products(self.db,"desk")],["Desk mat"])
  self.assertEqual(len(list_products(self.db,status="draft")),2)
 def test_edit_preserves_existing_data(self):
  updated=update_product(self.db,self.product["id"],{"title":"Premium desk mat","cost":180,"tags":["desk","office"]})
  self.assertEqual(updated["title"],"Premium desk mat")
  self.assertEqual(updated["data"]["selling_price"],499)
  self.assertEqual(updated["data"]["cost"],180)
 def test_status_transition_and_archive(self):
  update_product(self.db,self.product["id"],{"status":"research"})
  updated=update_product(self.db,self.product["id"],{"status":"archived"})
  self.assertEqual(updated["status"],"archived")
 def test_rejects_invalid_price_and_transition(self):
  with self.assertRaises(ValueError): update_product(self.db,self.product["id"],{"selling_price":-1})
  with self.assertRaises(ValueError): update_product(self.db,self.product["id"],{"status":"published"})
 def test_unknown_product(self):
  with self.assertRaises(ValueError): update_product(self.db,999,{"title":"Missing"})

if __name__=="__main__": unittest.main()
