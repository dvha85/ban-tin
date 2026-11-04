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
        article = migrated.import_article({'title': 'Tin mới sau nâng cấp',
            'url': 'https://example.com/post-upgrade', 'summary': 'Dữ liệu thử sau nâng cấp.'})
        bulletin = migrated.create_bulletin({'article_ids': [article['id']]})
        self.assertEqual(len(bulletin['items']), 1)
        def snapshot(room):
            with room.connection() as conn:
                names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
                return {name: [tuple(row) for row in conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
                        for name in names}
        before_restart = snapshot(migrated)
        Newsroom(self.directory)
        restarted = Newsroom(self.directory)
        self.assertEqual(snapshot(restarted), before_restart)
        self.assertEqual(restarted.export(draft['id']), before_export)
        with restarted.connection() as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertIsNone(conn.execute('PRAGMA foreign_key_check').fetchone())
        self.assertEqual(len(list((self.directory / 'backups').glob('pre-v04-*.sqlite3'))), 1)

    def test_restore_rejects_schema4_with_missing_constraints_or_foreign_keys(self):
        changes = {
            'index': 'DROP INDEX active_publication_position',
            'wrong_index': 'DROP INDEX active_publication_position',
            'columns': 'DROP TABLE publication_metrics',
            'no_fk': 'DROP TABLE publication_metrics',
            'legacy_table': 'DROP TABLE collection_settings',
            'legacy_column': 'ALTER TABLE collection_settings DROP COLUMN confirmed_at',
            'orphan': "INSERT INTO publication_metrics (publication_id,observed_at,payload,created_at) VALUES (999,'t','{}','t')",
        }
        for name, sql in changes.items():
            with self.subTest(name=name):
                backup = Path(self.room.backup())
                with closing(sqlite3.connect(backup)) as conn:
                    metrics_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='publication_metrics'").fetchone()[0]
                    conn.execute(sql)
                    if name == 'columns':
                        conn.execute('CREATE TABLE publication_metrics (id INTEGER PRIMARY KEY)')
                    if name == 'no_fk':
                        conn.execute(metrics_sql.replace('REFERENCES publications(id)', ''))
                    if name == 'wrong_index':
                        conn.execute('CREATE UNIQUE INDEX active_publication_position ON publications(variant_id, position) WHERE active=0')
                    conn.commit()
                    self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                target = self.directory / f'reject-{name}'
                with self.assertRaisesRegex(ValueError, 'cấu trúc|khóa ngoại'):
                    restore(backup, target)
                self.assertFalse(target.exists())
                self.assertTrue(backup.exists())

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
        restored_dir = self.directory / 'restored-upgraded-v3'
        restore(upgraded.backup(), restored_dir)
        restored = Newsroom(restored_dir)
        for draft_id, expected_export in expected['exports'].items():
            self.assertEqual(restored.export(int(draft_id)), expected_export)

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
                restored_dir = self.directory / f'restored-upgraded-v{version}'
                restore(upgraded.backup(), restored_dir)
                restored = Newsroom(restored_dir)
                for draft_id, expected_export in expected['exports'].items():
                    self.assertEqual(restored.export(int(draft_id)), expected_export)

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

    def test_migration_rejects_incompatible_structure_before_committing_version(self):
        fixture = Path(__file__).parent / 'fixtures' / 'legacy-v3.sql'
        cases = {
            'missing_legacy_column': 'ALTER TABLE drafts DROP COLUMN approved_hash',
            'incompatible_v4_table': 'CREATE TABLE bulletins (id INTEGER PRIMARY KEY, revision INTEGER)',
            'orphan_legacy_row': "INSERT INTO history (draft_id,action,snapshot,at) VALUES (99999,'fixture','{}','time')",
        }
        for name, mutation in cases.items():
            with self.subTest(case=name):
                target = self.directory / name
                target.mkdir()
                db = target / 'bantin.sqlite3'
                with closing(sqlite3.connect(db)) as conn:
                    conn.executescript(fixture.read_text(encoding='utf-8'))
                    conn.execute(mutation)
                    conn.commit()
                    before_schema = conn.execute(
                        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
                    ).fetchall()
                    before_drafts = conn.execute('SELECT * FROM drafts ORDER BY id').fetchall()
                    before_history = conn.execute('SELECT * FROM history ORDER BY id').fetchall()
                    self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
                with self.assertRaisesRegex(ValueError, 'cấu trúc|khóa ngoại'):
                    Newsroom(target)
                with closing(sqlite3.connect(db)) as conn:
                    self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
                    self.assertEqual(conn.execute(
                        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
                    ).fetchall(), before_schema)
                    self.assertEqual(conn.execute('SELECT * FROM drafts ORDER BY id').fetchall(), before_drafts)
                    self.assertEqual(conn.execute('SELECT * FROM history ORDER BY id').fetchall(), before_history)
                backups = list((target / 'backups').glob('pre-v04-*.sqlite3'))
                self.assertEqual(len(backups), 1)
                with closing(sqlite3.connect(backups[0])) as conn:
                    self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
                    self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_existing_v4_with_broken_contract_fails_without_writes(self):
        article = self.room.import_article({'title': 'Tin giả để kiểm tra schema 4',
            'url': 'https://example.com/v4-contract', 'summary': 'Dữ liệu giả.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']], 'title': 'Bản tin thử'})
        cases = {
            'missing_index': 'DROP INDEX active_publication_position',
            'missing_legacy_column': 'ALTER TABLE drafts DROP COLUMN approved_hash',
            'orphan': "INSERT INTO publication_metrics (publication_id,observed_at,payload,created_at) VALUES (99999,'t','{}','t')",
        }
        for name, mutation in cases.items():
            with self.subTest(case=name):
                target = self.directory / f'broken-v4-{name}'
                target.mkdir()
                db = target / 'bantin.sqlite3'
                with closing(sqlite3.connect(self.room.db_path)) as source, closing(sqlite3.connect(db)) as conn:
                    source.backup(conn)
                    conn.execute(mutation)
                    conn.commit()
                    before_schema = conn.execute(
                        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
                    ).fetchall()
                    before_bulletins = conn.execute('SELECT * FROM bulletins ORDER BY id').fetchall()
                    before_metrics = conn.execute('SELECT * FROM publication_metrics ORDER BY id').fetchall()
                    self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
                with self.assertRaisesRegex(ValueError, 'cấu trúc|khóa ngoại'):
                    Newsroom(target)
                with closing(sqlite3.connect(db)) as conn:
                    self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
                    self.assertEqual(conn.execute(
                        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
                    ).fetchall(), before_schema)
                    self.assertEqual(conn.execute('SELECT * FROM bulletins ORDER BY id').fetchall(), before_bulletins)
                    self.assertEqual(conn.execute('SELECT * FROM publication_metrics ORDER BY id').fetchall(), before_metrics)
                    self.assertEqual(before_bulletins[0][0], bulletin['id'])

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
        with closing(sqlite3.connect(target / 'bantin.sqlite3')) as conn:
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            previous_mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
        before = (target / 'bantin.sqlite3').read_bytes()
        with self.assertRaises(RuntimeError):
            Newsroom(target)
        self.assertEqual((target / 'bantin.sqlite3').read_bytes(), before)
        with closing(sqlite3.connect(target / 'bantin.sqlite3')) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 99)
            self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone()[0], previous_mode)

    def test_restore_interrupted_copy_removes_its_partial_destination(self):
        backup = self.room.backup()
        target = self.directory / 'restore-interrupted'
        real_connect = sqlite3.connect

        class FailingSource:
            def __init__(self, connection):
                self.connection = connection

            def __getattr__(self, name):
                return getattr(self.connection, name)

            def backup(self, destination):
                destination.execute('CREATE TABLE partial (id INTEGER)')
                destination.commit()
                raise OSError('simulated interrupted copy')

        def connect(path, *args, **kwargs):
            connection = real_connect(path, *args, **kwargs)
            return FailingSource(connection) if kwargs.get('uri') else connection

        with patch('newsroom.__main__.sqlite3.connect', side_effect=connect):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                restore(backup, target)
        self.assertFalse(target.exists())
        restore(backup, target)
        self.assertEqual(Newsroom(target).articles(), self.room.articles())

    def test_restore_failure_never_removes_other_files_in_destination(self):
        backup = self.room.backup()
        target = self.directory / 'restore-with-extra-file'
        real_connect = sqlite3.connect

        class FailingSource:
            def __init__(self, connection):
                self.connection = connection

            def __getattr__(self, name):
                return getattr(self.connection, name)

            def backup(self, destination):
                (target / 'other.txt').write_text('keep', encoding='utf-8')
                raise OSError('simulated interrupted copy')

        def connect(path, *args, **kwargs):
            connection = real_connect(path, *args, **kwargs)
            return FailingSource(connection) if kwargs.get('uri') else connection

        with patch('newsroom.__main__.sqlite3.connect', side_effect=connect):
            with self.assertRaises(OSError) as caught:
                restore(backup, target)
        self.assertEqual((target / 'other.txt').read_text(encoding='utf-8'), 'keep')
        self.assertFalse((target / 'bantin.sqlite3').exists())
        self.assertTrue(any('Không dọn được' in note for note in caught.exception.__notes__))

    def test_restore_copies_the_same_snapshot_that_was_validated(self):
        article = self.room.import_article({'title': 'Nguồn ban đầu',
            'url': 'https://example.com/restore-race', 'summary': 'Dữ liệu giả để thử.'})
        backup = self.room.backup()
        with closing(sqlite3.connect(backup)) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
        target = self.directory / 'restore-consistent'
        real_connect = sqlite3.connect

        class ConcurrentSource:
            def __init__(self, connection):
                self.connection = connection

            def __getattr__(self, name):
                return getattr(self.connection, name)

            def backup(self, destination):
                with closing(real_connect(backup)) as writer:
                    writer.execute('UPDATE articles SET title=? WHERE id=?', ('Thay đổi đồng thời', article['id']))
                    writer.execute('PRAGMA user_version=99')
                    writer.commit()
                return self.connection.backup(destination)

        def connect(path, *args, **kwargs):
            connection = real_connect(path, *args, **kwargs)
            return ConcurrentSource(connection) if kwargs.get('uri') else connection

        with patch('newsroom.__main__.sqlite3.connect', side_effect=connect):
            restore(backup, target)
        with closing(real_connect(target / 'bantin.sqlite3')) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
            self.assertEqual(conn.execute('SELECT title FROM articles WHERE id=?', (article['id'],)).fetchone()[0],
                             'Nguồn ban đầu')


if __name__ == '__main__':
    unittest.main()
