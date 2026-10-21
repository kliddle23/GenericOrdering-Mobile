"""Tests use fresh temporary SQLite databases, never the real order database."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from demo_edit_processor import create_disposable_db, apply_demo_request
from test_edit_validation import EditConflict, InvalidEdit

class DemoProcessorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fictional_orders.db"
        create_disposable_db(self.path)
        self.req = {"schema_version":1,"request_type":"update_order_lines",
                    "request_id":"demo-request-001","order_id":1,"expected_updated_at":"demo-v1",
                    "changes":[{"line_id":3,"field":"qty","expected":"1","value":"2"}]}
    def value(self):
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT qty FROM order_lines WHERE id=3").fetchone()[0]
    def test_apply_and_duplicate(self):
        self.assertEqual(apply_demo_request(self.path,self.req),"applied")
        self.assertEqual(self.value(),"2")
        self.assertEqual(apply_demo_request(self.path,self.req),"duplicate")
    def test_stale_request_rejected(self):
        self.req["expected_updated_at"]="old"
        with self.assertRaises(EditConflict): apply_demo_request(self.path,self.req)
        self.assertEqual(self.value(),"1")
    def test_duplicate_id_different_payload_rejected(self):
        apply_demo_request(self.path,self.req)
        self.req["changes"][0]["value"]="4"
        with self.assertRaises(InvalidEdit): apply_demo_request(self.path,self.req)
        self.assertEqual(self.value(),"2")
    def test_all_or_nothing(self):
        self.req["changes"].append({"line_id":999,"field":"notes","expected":"","value":"x"})
        with self.assertRaises(EditConflict): apply_demo_request(self.path,self.req)
        self.assertEqual(self.value(),"1")
    def test_reject_existing_file_creation(self):
        with self.assertRaises(FileExistsError): create_disposable_db(self.path)
    def test_reject_non_demo_db(self):
        other=Path(self.temp.name)/"other.db"
        with sqlite3.connect(other) as db: db.execute("CREATE TABLE orders (id INTEGER)")
        with self.assertRaises(InvalidEdit): apply_demo_request(other,self.req)

if __name__=="__main__": unittest.main()
