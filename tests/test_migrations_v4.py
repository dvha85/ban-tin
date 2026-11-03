import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from newsroom.__main__ import restore
from newsroom.migrations import migrate
from newsroom.service import Newsroom


class MigrationV4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.room = Newsroom(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def legacy_fixture(self):
        article = self.room.import_article({'title': 'Một bản tin nguồn thử nghiệm',
            'url': 'https://example.com/article', 'summary': 'Nguồn thử nghiệm có ghi chú kiểm chứng đủ dài.'})
        draft = self.room.create_draft(article['id'])
        draft = self.room.save_draft(draft['id'], {'revision': draft['revision'],
            'title': 'Tiêu đề bản tin thử nghiệm', 'body': 'Nội dung dùng để thử dữ liệu cũ. ' * 4,
            'angle': 'Giải thích một góc nhìn hữu ích.', 'page_name': 'Trang thử nghiệm'})
        draft = self.room.save_draft(draft['id'], {'revision': draft['revision'],
            'checks': {key: True for key in self.room.CHECKS}})
        draft = self.room.approve(draft['id'], draft['revision'])
        before_export = self.room.export(draft['id'])
        with self.room.connection() as conn:
            for table in ('publication_metrics', 'publication_events', 'publications', 'variant_approvals',
                          'content_variants', 'bulletin_items', 'bulletin_history', 'bulletins'):
                conn.execute('DROP TABLE ' + table)
            conn.execute('PRAGMA user_version=3')
            row = tuple(conn.execute('SELECT * FROM drafts WHERE id=?', (draft['id'],)).fetchone())
            history = [tuple(r) for r in conn.execute('SELECT * FROM history ORDER BY id')]
        return draft, before_export, row, history

    def test_migration_preserves_legacy_and_backups_and_is_idempotent(self):
        draft, before_export, before_row, before_history = self.legacy_fixture()
        migrated = Newsroom(self.directory)
        self.assertEqual(migrated.export(draft['id']), before_export)
        with migrated.connection() as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
            self.assertEqual(tuple(conn.execute('SELECT * FROM drafts WHERE id=?', (draft['id'],)).fetchone()), before_row)
            self.assertEqual([tuple(r) for r in conn.execute('SELECT * FROM history ORDER BY id')], before_history)
        backups = list((self.directory / 'backups').glob('pre-v04-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        Newsroom(self.directory)
        self.assertEqual(len(list((self.directory / 'backups').glob('pre-v04-*.sqlite3'))), 1)

    def test_failed_migration_rolls_back_all_tables_and_version(self):
        destination = self.directory / 'fault.sqlite3'
        with closing(sqlite3.connect(destination)) as conn:
            conn.execute('CREATE TABLE sentinel (value TEXT)')
            conn.execute("INSERT INTO sentinel VALUES ('unchanged')")
            conn.execute('PRAGMA user_version=3')
            conn.commit()
            with patch('newsroom.migrations.SCHEMA', ('CREATE TABLE new_table (id INTEGER)',
                                                       'CREATE TABLE invalid syntax here')):
                with self.assertRaises(sqlite3.Error):
                    migrate(conn, self.directory)
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertEqual(conn.execute('SELECT value FROM sentinel').fetchone()[0], 'unchanged')
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='new_table'").fetchone())

    def test_newer_version_fails_closed_and_restore_v4(self):
        backup = self.room.backup()
        target = self.directory / 'restored'
        restore(backup, target)
        restored = Newsroom(target)
        with restored.connection() as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
            conn.execute('PRAGMA user_version=99')
        with self.assertRaises(RuntimeError):
            Newsroom(target)
        with closing(sqlite3.connect(target / 'bantin.sqlite3')) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 99)


if __name__ == '__main__':
    unittest.main()
