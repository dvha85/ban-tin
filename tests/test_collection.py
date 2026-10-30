import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsroom.feeds import FeedError
from newsroom.service import Newsroom, ValidationError


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.room = Newsroom(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_new_sources_disabled_and_legacy_rss_enabled(self):
        sources = self.room.collection_sources()
        self.assertEqual(sum(s['enabled'] for s in sources), 4)
        self.assertTrue(any(s['kind'] == 'api' for s in sources))
        self.assertTrue(any(s['kind'] == 'web' for s in sources))

    def test_enable_requires_explicit_confirmation_and_known_id(self):
        with self.assertRaises(ValidationError):
            self.room.configure_source('typesafe', {'enabled': True})
        with self.assertRaises(ValidationError):
            self.room.configure_source('https://localhost', {'enabled': True, 'confirmed': True})
        self.room.configure_source('typesafe', {'enabled': True, 'confirmed': True})
        self.assertTrue(next(s for s in self.room.collection_sources() if s['id'] == 'typesafe')['enabled'])

    def test_fallback_is_idempotent_and_cannot_auto_run(self):
        first = self.room.queue_browser('typesafe', 'needs_interaction')
        second = self.room.queue_browser('typesafe', 'needs_interaction')
        self.assertEqual(first['id'], second['id'])
        with self.assertRaises(ValidationError):
            self.room.run_browser_job(first['id'], confirmed=False)
        self.assertEqual(self.room.collection_jobs()[0]['status'], 'pending')

    def test_unknown_job_is_never_requeued(self):
        job = self.room.queue_browser('typesafe', 'needs_interaction')
        with self.room.connection() as conn:
            conn.execute("UPDATE collection_jobs SET status='unknown' WHERE id=?", (job['id'],))
        self.assertEqual(self.room.queue_browser('typesafe', 'again')['status'], 'unknown')

    def test_restart_preserves_pending_and_disabled_sources(self):
        job = self.room.queue_browser('typesafe', 'needs_interaction')
        restarted = Newsroom(self.room.data_dir)
        self.assertEqual(restarted.collection_jobs()[0]['id'], job['id'])
        self.assertEqual(sum(s['enabled'] for s in restarted.collection_sources()), 4)

    def test_cancel_does_not_ingest_or_approve(self):
        job = self.room.queue_browser('typesafe', 'needs_interaction')
        self.room.cancel_browser_job(job['id'])
        self.assertEqual(self.room.collection_jobs()[0]['status'], 'cancelled')
        self.assertEqual(self.room.articles(), [])
        self.assertEqual(self.room.drafts(), [])


class ParserTests(unittest.TestCase):
    def test_public_policy_rejects_other_host_paths_and_private_ips(self):
        from newsroom.collection import validate_target, source_by_id
        source = source_by_id('typesafe')
        for url in ('http://typesafe.ai/blog/a', 'https://typesafe.ai.evil.com/blog/a',
                    'https://127.0.0.1/blog/a', 'https://typesafe.ai/settings',
                    'https://typesafe.ai/blog/../settings', 'https://typesafe.ai/blog/%2e%2e/settings'):
            with self.assertRaises(FeedError):
                validate_target(url, source, resolve=False)

    def test_api_only_published_releases_with_expected_repository(self):
        from newsroom.collection import parse_api, source_by_id
        source = source_by_id('github-crawl4ai')
        raw = json.dumps([
            {'name': 'New crawler release', 'html_url': 'https://github.com/unclecode/crawl4ai/releases/tag/v1',
             'body': 'Details', 'published_at': '2026-10-14T12:00:00Z', 'draft': False},
            {'name': 'Wrong repo', 'html_url': 'https://github.com/evil/other/releases/tag/v1'},
            {'name': 'Draft', 'html_url': 'https://github.com/unclecode/crawl4ai/releases/tag/v2', 'draft': True},
        ]).encode()
        items = parse_api(raw, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['date_kind'], 'published')

    def test_web_discovery_scoped_and_not_entire_site(self):
        from newsroom.collection import discover_links, source_by_id
        source = source_by_id('typesafe')
        raw = '<a href="/blog/new-model">New model announcement</a><a href="/login">Login</a><a href="https://evil.com/blog/x">Other</a>'
        self.assertEqual(discover_links(raw, source), ['https://typesafe.ai/blog/new-model'])

    def test_page_extract_keeps_provenance_not_invented_date(self):
        from newsroom.collection import extract_page, source_by_id
        raw = '<html><head><meta property="og:title" content="A new model"></head><body><nav>ignore</nav><article><h1>A new model</h1><p>' + 'Article evidence. ' * 20 + '</p></article></body></html>'
        item = extract_page(raw, 'https://typesafe.ai/blog/new-model', source_by_id('typesafe'))
        self.assertIsNone(item['published_at'])
        self.assertEqual(item['date_kind'], 'unknown')
        self.assertNotIn('ignore', item['summary'])
        self.assertEqual(item['collection_method'], 'crawl4ai')
        self.assertEqual(len(item['content_hash']), 64)

    def test_paywall_and_short_empty_content_not_success(self):
        from newsroom.collection import extract_page, source_by_id
        for raw in ('<h1>Just a moment</h1><p>Verify you are human</p>',
                    '<h1>A title</h1><p>Short.</p>'):
            with self.assertRaises(FeedError):
                extract_page(raw, 'https://typesafe.ai/blog/new-model', source_by_id('typesafe'))

    def test_robots_fail_closed_and_honor_disallow(self):
        from newsroom.collection import check_robots, source_by_id
        source = source_by_id('typesafe')
        with patch('newsroom.collection.fetch_bytes', return_value=b'User-agent: *\nDisallow: /blog/'):
            with self.assertRaises(FeedError):
                check_robots(source['url'] + '/article', source)
        with patch('newsroom.collection.fetch_bytes', side_effect=FeedError('HTTP 503')):
            with self.assertRaises(FeedError):
                check_robots(source['url'], source)

    def test_private_dns_is_rejected(self):
        from newsroom.collection import validate_target, source_by_id
        with patch('newsroom.feeds.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(FeedError):
                validate_target('https://typesafe.ai/blog/a', source_by_id('typesafe'))

    def test_subprocess_timeout_is_not_retried(self):
        import subprocess
        from newsroom.collection import run_worker
        with patch('newsroom.collection.subprocess.run', side_effect=subprocess.TimeoutExpired(['python'], 2)) as run:
            with self.assertRaises(FeedError):
                run_worker('crawl', {}, timeout=2, python=__import__('sys').executable)
        self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
