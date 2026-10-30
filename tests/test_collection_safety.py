import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

from newsroom.collection import (AccessBlocked, FeedError, NeedsBrowser, collect_web,
                                 extract_page, run_worker, source_by_id)
from newsroom.service import Newsroom, ValidationError


HTML = '<main><h1>Public news announcement</h1><p>' + 'Verified fixture evidence only. ' * 20 + '</p></main>'
URL = 'https://typesafe.ai/blog/example-news'


class DurableCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.room = Newsroom(Path(self.temp.name))
        self.source = source_by_id('typesafe')
        self.room.configure_source('typesafe', {'enabled': True, 'confirmed': True})

    def tearDown(self):
        self.temp.cleanup()

    def config(self, quota=1):
        return {'max_jobs_per_day': quota, 'hermes_root': self.temp.name}, 'fixture-key'

    def run_job(self, job, result=None, error=None, quota=1):
        with patch.object(self.room, 'browser_settings', return_value=self.config(quota)), \
                patch('newsroom.collection_service.tools_python', return_value=sys.executable), \
                patch('newsroom.collection_service.run_worker', return_value=result, side_effect=error) as worker:
            value = self.room.run_browser_job(job['id'], confirmed=True)
        return value, worker

    def test_completed_job_ingests_only_evidence_not_drafts(self):
        job = self.room.queue_browser('typesafe', 'fixture')
        result, worker = self.run_job(job, {'pages': [{'url': URL, 'html': HTML}]})
        self.assertEqual(result['added'], 1)
        self.assertEqual(worker.call_count, 1)
        self.assertEqual(self.room.collection_jobs()[0]['status'], 'completed')
        self.assertEqual(self.room.articles()[0]['sources'][0]['collection_method'], 'hermes-browser-use')
        self.assertEqual(self.room.drafts(), [])

    def test_cancelled_unknown_still_consumes_quota_after_restart(self):
        job = self.room.queue_browser('typesafe', 'fixture')
        with self.assertRaises(ValidationError):
            self.run_job(job, error=FeedError('timeout'))
        self.assertEqual(self.room.collection_jobs()[0]['status'], 'unknown')
        self.room.cancel_browser_job(job['id'])
        self.room = Newsroom(self.room.data_dir)
        next_job = self.room.queue_browser('typesafe', 'new explicit request')
        with patch.object(self.room, 'browser_settings', return_value=self.config()), \
                patch('newsroom.collection_service.run_worker') as worker:
            with self.assertRaises(ValidationError):
                self.room.run_browser_job(next_job['id'], confirmed=True)
            worker.assert_not_called()
        with self.room.connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM collection_attempts').fetchone()[0], 1)

    def test_non_pending_or_disabled_cannot_launch(self):
        job = self.room.queue_browser('typesafe', 'fixture')
        self.room.configure_source('typesafe', {'enabled': False})
        with patch.object(self.room, 'browser_settings', return_value=self.config()), \
                patch('newsroom.collection_service.run_worker') as worker:
            for job_id in (job['id'], 99999):
                with self.assertRaises(ValidationError):
                    self.room.run_browser_job(job_id, confirmed=True)
            worker.assert_not_called()

    def test_invalid_connection_file_fails_closed_with_clear_error(self):
        path = self.room.data_dir / 'browser-connection.json'
        for value in ([], None, {'enabled': True}, 'x' * 17000):
            path.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaises(ValidationError):
                self.room.browser_settings()

    def test_unreadable_key_is_not_exposed_or_treated_as_connected(self):
        root = self.room.data_dir / 'fixture-hermes'
        (root / 'venv/Scripts').mkdir(parents=True)
        (root / 'run_agent.py').touch()
        (root / 'venv/Scripts/python.exe').touch()
        config = dict(enabled=True, model='fixture/model', provider='openrouter',
                      hermes_root=str(root), max_jobs_per_day=1)
        (self.room.data_dir / 'browser-connection.json').write_text(json.dumps(config), encoding='utf-8')
        (self.room.data_dir / 'browser-key.txt').write_bytes(b'\xff\xfe\x00')
        with patch.dict(os.environ, {}, clear=True), \
                patch('newsroom.collection_service.tools_python', return_value=sys.executable):
            with self.assertRaises(ValidationError):
                self.room.browser_settings()

    def test_stale_running_becomes_unknown_not_pending(self):
        job = self.room.queue_browser('typesafe', 'fixture')
        with self.room.connection() as conn:
            conn.execute("UPDATE collection_jobs SET status='running',updated_at='2000-01-01T00:00:00Z' WHERE id=?", (job['id'],))
        self.room = Newsroom(self.room.data_dir)
        self.assertEqual(self.room.collection_jobs()[0]['status'], 'unknown')
        self.assertEqual(self.room.queue_browser('typesafe', 'retry')['id'], job['id'])

    def test_running_cannot_be_cancelled_or_double_started(self):
        job = self.room.queue_browser('typesafe', 'fixture')
        with patch.object(self.room, 'browser_settings', return_value=self.config()):
            self.room.prepare_browser_job(job['id'], confirmed=True)
            with self.assertRaises(ValidationError):
                self.room.prepare_browser_job(job['id'], confirmed=True)
        with self.assertRaises(ValidationError):
            self.room.cancel_browser_job(job['id'])

    def test_malformed_or_out_of_scope_agent_output_never_partially_imports(self):
        for pages in ([], [None], [{'url': 'https://evil.example/blog/a', 'html': HTML}],
                      [{'url': URL, 'html': 'x' * 2_000_001}],
                      [{'url': URL, 'html': HTML}, {'url': URL, 'html': None}],
                      [{'url': URL, 'html': '<h1>Just a moment</h1>Verify you are human'}]):
            with self.subTest(pages=str(pages)[:80]):
                job = self.room.queue_browser('typesafe', 'fixture')
                with self.assertRaises(ValidationError):
                    self.run_job(job, {'pages': pages}, quota=3)
                self.assertEqual(self.room.articles(), [])
                self.assertEqual(self.room.drafts(), [])
                self.room.cancel_browser_job(job['id'])
                # Separate 24h windows for independent fixtures, not a production reset API.
                with self.room.connection() as conn:
                    conn.execute("UPDATE collection_attempts SET started_at='2000-01-01T00:00:00Z'")

    def test_block_or_network_failure_never_queues_ai(self):
        for error in (AccessBlocked('robots disallow'), FeedError('network failure')):
            with patch('newsroom.service.fetch_feed', return_value=[]), \
                    patch.object(self.room, 'collect_non_rss', side_effect=error), \
                    patch('newsroom.collection_service.run_worker') as worker:
                self.room.refresh()
                worker.assert_not_called()
            self.assertEqual(self.room.collection_jobs(), [])
        with patch('newsroom.service.fetch_feed', return_value=[]), \
                patch.object(self.room, 'collect_non_rss', side_effect=NeedsBrowser('needs interaction')):
            self.room.refresh()
            self.room.refresh()
        self.assertEqual(len(self.room.collection_jobs()), 1)
        self.assertEqual(self.room.collection_jobs()[0]['status'], 'pending')

    def approved(self):
        item = extract_page(HTML, URL, self.source)
        self.room.ingest(self.source, [item])
        draft = self.room.create_draft(self.room.articles()[0]['id'])
        draft = self.room.save_draft(draft['id'], {
            'revision': draft['revision'], 'title': 'Bài kiểm thử quy trình nâng cấp',
            'body': 'Nội dung minh họa kiểm thử, không phải tin thật. ' * 5,
            'angle': 'Giải thích bằng chứng và giới hạn.', 'page_name': 'Page minh họa'})
        draft = self.room.save_draft(draft['id'], {'revision': draft['revision'],
                                                 'checks': {k: True for k in self.room.CHECKS}})
        return self.room.approve(draft['id'], draft['revision'])

    def test_candidate_refresh_does_not_change_approved_snapshot(self):
        draft = self.approved()
        before = self.room.export(draft['id'])
        changed = extract_page(HTML.replace('Verified', 'Changed'), URL, self.source)
        self.room.ingest(self.source, [changed])
        self.assertEqual(self.room.export(draft['id']), before)
        same = self.room.save_draft(draft['id'], {'revision': draft['revision'], 'sources': draft['sources']})
        self.assertEqual(same['status'], 'approved')
        self.assertEqual(same['sources'], draft['sources'])
        edited = [dict(same['sources'][0], summary='Ghi chú do người dùng sửa, không còn là trích đoạn gốc.')]
        changed = self.room.save_draft(same['id'], {'revision': same['revision'], 'sources': edited})
        self.assertEqual(changed['status'], 'draft')
        self.assertNotIn('content_hash', changed['sources'][0])

    def test_v1_migration_backs_up_and_preserves_approved_export(self):
        draft = self.approved()
        # Recreate a real v1-shaped payload: old drafts do not contain provenance.
        with self.room.connection() as conn:
            row = conn.execute('SELECT payload FROM drafts WHERE id=?', (draft['id'],)).fetchone()
            payload = json.loads(row[0])
            for source in payload['sources']:
                for key in ('collection_method', 'scope', 'content_hash', 'excerpt_hash'):
                    source.pop(key, None)
            old = dict(draft, **payload)
            conn.execute('UPDATE drafts SET payload=?,approved_hash=? WHERE id=?',
                         (json.dumps(payload, ensure_ascii=False), self.room._hash(old), draft['id']))
            for table in ('collection_attempts', 'collection_jobs', 'collection_settings', 'collection_evidence'):
                conn.execute('DROP TABLE ' + table)
            conn.execute('PRAGMA user_version=1')
        before = self.room.export(draft['id'])
        self.room = Newsroom(self.room.data_dir)
        self.assertEqual(self.room.export(draft['id']), before)
        backups = list((self.room.data_dir / 'backups').glob('pre-v02-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        conn = sqlite3.connect(backups[0])
        try:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        finally:
            conn.close()
        Newsroom(self.room.data_dir)
        self.assertEqual(len(list((self.room.data_dir / 'backups').glob('pre-v02-*.sqlite3'))), 1)


class CollectorProtocolTests(unittest.TestCase):
    def test_worker_result_protocol_and_environment(self):
        def completed(*args, **kwargs):
            self.assertFalse(kwargs['shell'])
            self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
            self.assertNotIn('GITHUB_TOKEN', kwargs['env'])
            kwargs['stdout'].write(b'library log\nBANTIN_RESULT:{"ok":true,"pages":[]}\n')
            return subprocess.CompletedProcess(args[0], 0)
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'not-a-key', 'GITHUB_TOKEN': 'not-a-token'}), \
                patch('newsroom.collection.subprocess.run', side_effect=completed):
            self.assertTrue(run_worker('crawl', {}, python=sys.executable)['ok'])

    def test_invalid_protocol_or_failed_exit_not_success(self):
        for data, code in (([], 0), ({'ok': 'yes'}, 0), ({'ok': True}, 7)):
            def completed(*args, **kwargs):
                kwargs['stdout'].write(('BANTIN_RESULT:' + json.dumps(data)).encode())
                return subprocess.CompletedProcess(args[0], code)
            with patch('newsroom.collection.subprocess.run', side_effect=completed):
                with self.assertRaises(FeedError):
                    run_worker('crawl', {}, python=sys.executable)

    def test_transport_error_and_blocked_index_never_become_interaction(self):
        source = source_by_id('typesafe')
        index = {'ok': True, 'url': source['url'],
                 'html': '<a href="/blog/example-news">Article announcement</a>'}
        with patch('newsroom.collection.check_robots', return_value=1), \
                patch('newsroom.collection.run_worker', side_effect=[index, FeedError('tool unavailable')]):
            with self.assertRaises(FeedError) as error:
                collect_web(source)
            self.assertNotIsInstance(error.exception, NeedsBrowser)
        with patch('newsroom.collection.check_robots', return_value=1), \
                patch('newsroom.collection.run_worker', return_value={
                    'url': source['url'], 'html': '<h1>Just a moment</h1>Verify you are human'}):
            with self.assertRaises(AccessBlocked):
                collect_web(source)


class BrowserGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_guard_only_allows_scoped_read_requests(self):
        from newsroom.collect_worker import guard_context
        context = SimpleNamespace(route=AsyncMock(), route_web_socket=AsyncMock())
        await guard_context(context, source_by_id('typesafe'))
        handler = context.route.call_args.args[1]
        for url, method, kind, allowed in (
                (URL, 'GET', 'document', True),
                (URL, 'POST', 'fetch', False),
                ('https://typesafe.ai/account', 'GET', 'document', False),
                ('https://evil.example/blog/a', 'GET', 'script', False),
                (URL, 'GET', 'image', False)):
            route = SimpleNamespace(request=SimpleNamespace(url=url, method=method, resource_type=kind),
                                    continue_=AsyncMock(), abort=AsyncMock())
            with patch('newsroom.collection.public_ip', return_value='1.1.1.1'), \
                    patch('newsroom.collect_worker.check_robots', return_value=1), \
                    patch('newsroom.collect_worker.asyncio.sleep', new_callable=AsyncMock):
                await handler(route)
            self.assertEqual(route.continue_.await_count, int(allowed))
            self.assertEqual(route.abort.await_count, int(not allowed))

    async def test_guard_aborts_robots_disallowed_document(self):
        from newsroom.collect_worker import guard_context
        context = SimpleNamespace(route=AsyncMock(), route_web_socket=AsyncMock())
        await guard_context(context, source_by_id('typesafe'))
        handler = context.route.call_args.args[1]
        route = SimpleNamespace(request=SimpleNamespace(url=URL, method='GET', resource_type='document'),
                                continue_=AsyncMock(), abort=AsyncMock())
        with patch('newsroom.collection.public_ip', return_value='1.1.1.1'), \
                patch('newsroom.collect_worker.check_robots', side_effect=AccessBlocked('robots')):
            await handler(route)
        route.continue_.assert_not_awaited()
        route.abort.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
