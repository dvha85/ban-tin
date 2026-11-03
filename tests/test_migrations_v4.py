import json
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

    def test_real_v3_fixture_preserves_all_legacy_rows_and_approved_exports(self):
        fixture_dir = Path(__file__).parent / 'fixtures'
        expected = json.loads((fixture_dir / 'legacy-v3-expected.json').read_text(encoding='utf-8'))
        target = self.directory / 'actual-v3'
        target.mkdir()
        with closing(sqlite3.connect(target / 'bantin.sqlite3')) as conn:
            conn.executescript((fixture_dir / 'legacy-v3.sql').read_text(encoding='utf-8'))
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
        upgraded = Newsroom(target)
        with upgraded.connection() as conn:
            for table in ('articles', 'article_sources', 'drafts', 'history', 'metrics', 'custom_sources', 'collection_settings'):
                with self.subTest(table=table):
                    actual = [dict(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                    self.assertEqual(actual, expected[table])
        for draft_id, expected_export in expected['exports'].items():
            self.assertEqual(upgraded.export(int(draft_id)), expected_export)
        self.assertEqual([draft['status'] for draft in sorted(upgraded.drafts(), key=lambda draft: draft['id'])],
                         ['draft', 'approved', 'published'])
        backup = list((target / 'backups').glob('pre-v04-*.sqlite3'))
        self.assertEqual(len(backup), 1)
        with closing(sqlite3.connect(backup[0])) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM drafts').fetchone()[0], 3)

    def test_upgrade_reduced_schema_1_and_2_preserves_legacy_exports(self):
        fixture_dir = Path(__file__).parent / 'fixtures'
        expected = json.loads((fixture_dir / 'legacy-v3-expected.json').read_text(encoding='utf-8'))
        for version in (1, 2):
            with self.subTest(version=version):
                target = self.directory / f'synthetic-v{version}'
                target.mkdir()
                with closing(sqlite3.connect(target / 'bantin.sqlite3')) as conn:
                    conn.executescript((fixture_dir / 'legacy-v3.sql').read_text(encoding='utf-8'))
                    conn.execute("DELETE FROM collection_settings WHERE source_id='custom-fixture'")
                    conn.execute('DROP TABLE custom_sources')
                    if version == 1:
                        for name in ('collection_attempts', 'collection_evidence', 'collection_jobs', 'collection_settings'):
                            conn.execute('DROP TABLE ' + name)
                    conn.execute(f'PRAGMA user_version={version}')
                    conn.commit()
                upgraded = Newsroom(target)
                for draft_id, expected_export in expected['exports'].items():
                    self.assertEqual(upgraded.export(int(draft_id)), expected_export)
                with upgraded.connection() as conn:
                    self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
                    for table in ('drafts', 'history', 'metrics'):
                        self.assertEqual([dict(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY rowid')], expected[table])
                self.assertEqual(len(list((target / 'backups').glob(f'pre-v0{version + 1}-*.sqlite3'))), 1)

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

    def test_unversioned_nonempty_database_is_backed_up_before_migration(self):
        destination = self.directory / 'unversioned.sqlite3'
        with closing(sqlite3.connect(destination)) as conn:
            conn.execute('CREATE TABLE sentinel (value TEXT)')
            conn.execute("INSERT INTO sentinel VALUES ('keep')")
            conn.commit()
            migrate(conn, self.directory)
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
        backups = list((self.directory / 'backups').glob('pre-unversioned-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as backup:
            self.assertEqual(backup.execute('PRAGMA user_version').fetchone()[0], 0)
            self.assertEqual(backup.execute('SELECT value FROM sentinel').fetchone()[0], 'keep')

    def test_backup_failure_leaves_old_version_and_schema_untouched(self):
        destination = self.directory / 'backup-failure.sqlite3'
        with closing(sqlite3.connect(destination)) as conn:
            conn.execute('CREATE TABLE sentinel (value TEXT)')
            conn.execute("INSERT INTO sentinel VALUES ('untouched')")
            conn.execute('PRAGMA user_version=3')
            conn.commit()
            with patch('newsroom.migrations.sqlite3.connect', side_effect=OSError('backup unavailable')):
                with self.assertRaises(OSError):
                    migrate(conn, self.directory)
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertEqual(conn.execute('SELECT value FROM sentinel').fetchone()[0], 'untouched')
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='bulletins'").fetchone())

    def test_concurrent_write_during_backup_aborts_migration(self):
        destination = self.directory / 'concurrent.sqlite3'
        with closing(sqlite3.connect(destination)) as conn:
            conn.execute('CREATE TABLE sentinel (value TEXT)')
            conn.execute('PRAGMA user_version=3')
            conn.commit()

            def other_writer(_):
                with closing(sqlite3.connect(destination)) as other:
                    other.execute("INSERT INTO sentinel VALUES ('concurrent')")
                    other.commit()
                return 'fixture'

            with patch('newsroom.migrations.secrets.token_hex', side_effect=other_writer):
                with self.assertRaisesRegex(RuntimeError, 'vừa thay đổi'):
                    migrate(conn, self.directory)
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertEqual(conn.execute('SELECT value FROM sentinel').fetchone()[0], 'concurrent')
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='bulletins'").fetchone())

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
