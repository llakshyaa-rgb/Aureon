import tempfile
import unittest
from pathlib import Path
from aureon.db import initialize
from aureon.workflows import initialize_workspace, create_record, list_records
from aureon.backups import backup_database, list_backups, restore_backup


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "aureon.sqlite3"
        self.backup_dir = self.root / "backups"
        initialize(self.db)
        initialize_workspace(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_backup_is_integrity_checked_and_restore_preserves_snapshot(self):
        create_record(self.db, "product", "Before backup", {"selling_price": 10})
        backup = backup_database(self.db, self.backup_dir)
        create_record(self.db, "product", "After backup", {"selling_price": 20})
        restored = restore_backup(self.db, backup["path"], self.backup_dir)
        self.assertEqual(restored["integrity"], "ok")
        self.assertIsNotNone(restored["pre_restore_backup"])
        records = list_records(self.db, "product")
        self.assertEqual([item["title"] for item in records], ["Before backup"])
        self.assertGreaterEqual(len(list_backups(self.db, self.backup_dir)), 2)

    def test_backup_retention_is_bounded(self):
        for _ in range(3):
            backup_database(self.db, self.backup_dir, retain=2)
        self.assertEqual(len(list_backups(self.db, self.backup_dir)), 2)

    def test_invalid_backup_options_rejected(self):
        with self.assertRaises(ValueError):
            backup_database(self.db, self.backup_dir, retain=0)
        with self.assertRaises(ValueError):
            restore_backup(self.db, self.db, self.backup_dir)


if __name__ == "__main__":
    unittest.main()
