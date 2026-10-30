import io
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from newsroom.collection import AccessBlocked, source_by_id
from newsroom.feeds import FeedError
from newsroom.service import Newsroom, ValidationError


FEED = b'''<rss version="2.0"><channel><title>Example feed</title><item>
<title>A useful technology update</title><link>https://dev.to/member/technology-update</link>
<description>A short public excerpt.</description></item></channel></rss>'''
HOME = '<html><head><link rel="alternate" type="application/rss+xml" href="/feed/"></head></html>'.encode()


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.room = Newsroom(Path(self.temp.name))
        self.data = dict(name='DEV Community', url='https://dev.to/', kind='auto', confirmed=True)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, **changes):
        with patch('newsroom.subscriptions.read_public', side_effect=[
                (HOME, 'https://dev.to/'), (FEED, 'https://dev.to/feed/')]):
            return self.room.add_source(dict(self.data, **changes))

    def test_homepage_discovers_rss_and_persists_as_enabled_subscription_not_article(self):
        source = self.add()
        self.assertEqual(source['kind'], 'rss')
        self.assertTrue(source['custom'])
        self.assertTrue(source['enabled'])
        self.assertEqual(source['url'], 'https://dev.to/feed/')
        self.assertEqual(len(self.room.collection_sources()), 8)
        self.assertEqual(self.room.articles(), [])
        self.assertEqual(self.room.drafts(), [])
        restarted = Newsroom(self.room.data_dir)
        self.assertEqual(next(s for s in restarted.collection_sources() if s['id'] == source['id']), source)

    def test_direct_atom_or_rss_url_uses_bounded_pinned_transport(self):
        with patch('newsroom.subscriptions.read_public', return_value=(FEED, 'https://dev.to/feed')):
            source = self.room.add_source(dict(self.data, kind='rss', url='https://dev.to/feed'))
        with patch('newsroom.subscriptions.read_public', return_value=(FEED, source['url'])) as read, \
                patch('newsroom.service.fetch_feed', return_value=[]):
            self.room.refresh()
        self.assertEqual(read.call_count, 1)
        self.assertEqual(len(self.room.articles()), 1)
        self.assertEqual(self.room.articles()[0]['source_name'], 'DEV Community')
        self.assertEqual(self.room.drafts(), [])

    def test_declared_relative_atom_and_malformed_html_attributes(self):
        home = b'<html><head><link rel type href="/bad"><link rel="alternate" type="application/atom+xml" href="feed.xml"></head></html>'
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><title>Example</title><entry><title>Public update</title><link href="https://dev.to/blog/update"/></entry></feed>'
        with patch('newsroom.subscriptions.read_public', side_effect=[
                (home, 'https://dev.to/blog/'), (atom, 'https://dev.to/blog/feed.xml')]) as read:
            source = self.room.add_source(dict(self.data, url='https://dev.to/blog/'))
        self.assertEqual(source['url'], 'https://dev.to/blog/feed.xml')
        self.assertEqual(read.call_args.args[0], 'https://dev.to/blog/feed.xml')

    def test_missing_candidate_can_try_next_feed_but_permission_denial_cannot(self):
        from newsroom.collection import PageNotFound
        html = b'<html><head><link rel="alternate" type="application/rss+xml" href="/missing"></head></html>'
        with patch('newsroom.subscriptions.read_public', side_effect=[
                (html, 'https://dev.to/'), PageNotFound('404'), (FEED, 'https://dev.to/feed')]) as read:
            self.room.add_source(self.data)
        self.assertEqual(read.call_count, 3)
        with patch('newsroom.subscriptions.read_public', side_effect=[
                (html, 'https://other.example/'), AccessBlocked('403')]) as read:
            with self.assertRaises(ValidationError):
                self.room.add_source(dict(self.data, url='https://other.example/'))
        self.assertEqual(read.call_count, 2)

    def test_disabling_custom_source_keeps_articles_and_stops_refresh(self):
        source = self.add()
        self.room.import_article(dict(title='Manual reference', url='https://dev.to/reference', summary='Notes'))
        self.room.configure_source(source['id'], {'enabled': False})
        with patch('newsroom.subscriptions.read_public') as read, \
                patch('newsroom.service.fetch_feed', return_value=[]):
            self.room.refresh()
            read.assert_not_called()
        self.assertEqual(len(self.room.articles()), 1)
        self.room.configure_source(source['id'], {'enabled': True, 'confirmed': True})

    def test_missing_confirmation_demo_and_bad_fields_do_not_fetch_or_save(self):
        invalid = [dict(confirmed=False), dict(kind='api'), dict(name=[]), dict(url=7),
                   dict(url='http://dev.to/'), dict(url='https://127.0.0.1/feed'),
                   dict(url='https://dev.to/feed?api_key=secret')]
        with patch('newsroom.subscriptions.read_public') as read:
            for changes in invalid:
                with self.subTest(changes=changes), self.assertRaises(ValidationError):
                    self.room.add_source(dict(self.data, **changes))
            read.assert_not_called()
        self.room.demo = True
        with self.assertRaises(ValidationError):
            self.room.add_source(self.data)
        self.assertEqual(len(self.room.collection_sources()), 7)

    def test_duplicates_by_home_feed_or_catalog_are_reported_without_new_source(self):
        self.add()
        for url in ('https://dev.to/', 'https://dev.to/feed/', 'https://dev.to/feed?utm_source=test',
                    'https://blog.google/rss/'):
            with self.subTest(url=url), patch('newsroom.subscriptions.read_public') as read:
                with self.assertRaises(ValidationError):
                    self.room.add_source(dict(self.data, url=url))
                read.assert_not_called()
        self.assertEqual(len(self.room.collection_sources()), 8)

    def test_feed_detected_from_other_input_still_deduplicates_atomically(self):
        self.add()
        with patch('newsroom.subscriptions.read_public', side_effect=[
                (HOME, 'https://dev.to/latest'), (FEED, 'https://dev.to/feed/')]):
            with self.assertRaises(ValidationError):
                self.room.add_source(dict(self.data, url='https://dev.to/latest'))
        self.assertEqual(len(self.room.collection_sources()), 8)

    def test_concurrent_add_only_one_subscription_is_created(self):
        def add(_):
            try:
                return self.room.add_source(dict(self.data, url='https://dev.to/feed', kind='rss'))['id']
            except ValidationError:
                return 'duplicate'
        with patch('newsroom.subscriptions.read_public', return_value=(FEED, 'https://dev.to/feed')):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(add, range(2)))
        self.assertEqual(results.count('duplicate'), 1)
        self.assertEqual(len(self.room.collection_sources()), 8)

    def test_no_feed_does_not_silently_fallback_to_browser_or_ai(self):
        with patch('newsroom.subscriptions.read_public', return_value=(b'<html><h1>News</h1></html>', 'https://dev.to/')), \
                patch('newsroom.collection.run_worker') as worker:
            with self.assertRaises(ValidationError):
                self.room.add_source(self.data)
            worker.assert_not_called()
        self.assertEqual(self.room.collection_jobs(), [])
        self.assertEqual(len(self.room.collection_sources()), 7)

    def test_limit_is_checked_before_network_and_under_write_lock(self):
        from newsroom.subscriptions import MAX_CUSTOM_SOURCES
        with self.room.connection() as conn:
            for number in range(MAX_CUSTOM_SOURCES):
                url = f'https://example.org/feed/{number}'
                conn.execute('INSERT INTO custom_sources VALUES (?,?,?,?,?,?,?,?,?)',
                             ('custom-' + f'{number:032x}', f'Source {number}', 'rss', url, url,
                              url, 'https://example.org/', '', '2026-10-16T00:00:00Z'))
        with patch('newsroom.subscriptions.read_public') as read:
            with self.assertRaises(ValidationError):
                self.room.add_source(self.data)
            read.assert_not_called()

    def test_web_requires_explicit_path_scope_and_passes_snapshot_to_worker(self):
        with patch('newsroom.subscriptions.read_public') as read:
            for prefix in ('', 'blog/', '/blog', '/blog/../', '/blog/%2f/', '/blog/?x=1'):
                with self.subTest(prefix=prefix), self.assertRaises(ValidationError):
                    self.room.add_source(dict(self.data, kind='web', prefix=prefix))
            read.assert_not_called()
        with patch('newsroom.subscriptions.read_public', return_value=(b'<html>Public news</html>', 'https://dev.to/news')):
            source = self.room.add_source(dict(self.data, kind='web', url='https://dev.to/news', prefix='/news/'))
        from newsroom.collection import validate_target, collect_web, NeedsBrowser
        self.assertEqual(validate_target('https://dev.to/news/article', source, resolve=False), 'https://dev.to/news/article')
        with self.assertRaises(FeedError):
            validate_target('https://dev.to/account', source, resolve=False)
        with patch('newsroom.collection.check_robots', return_value=1), \
                patch('newsroom.collection.run_worker', return_value={'url': source['url'], 'html': '<html>No links</html>'}) as run:
            with self.assertRaises(NeedsBrowser):
                collect_web(source)
        self.assertEqual(run.call_args.args[1]['source'], source)
        job = self.room.queue_browser(source['id'], 'Need interaction')
        self.room.configure_source(source['id'], {'enabled': False})
        self.assertEqual(self.room.collection_jobs()[0]['status'], 'cancelled')
        self.assertEqual(job['source_id'], source['id'])

    def test_failed_network_robots_or_malformed_feed_do_not_create_source(self):
        for error in (FeedError('network'), AccessBlocked('robots')):
            with self.subTest(error=error), patch('newsroom.subscriptions.read_public', side_effect=error):
                with self.assertRaises(ValidationError):
                    self.room.add_source(self.data)
        with patch('newsroom.subscriptions.read_public', return_value=(b'<rss>broken', 'https://dev.to/feed')):
            with self.assertRaises(ValidationError):
                self.room.add_source(dict(self.data, kind='rss', url='https://dev.to/feed'))
        self.assertEqual(len(self.room.collection_sources()), 7)

    def test_v2_migration_backup_and_custom_source_backup_restore(self):
        item = self.room.import_article(dict(title='Preserved manual article', url='https://dev.to/notes',
            summary='Ghi chú bằng chứng kiểm thử thủ công, không phải tin thật.'))
        draft = self.room.create_draft(item['id'])
        draft = self.room.save_draft(draft['id'], dict(revision=draft['revision'],
            title='Bản kiểm thử đã duyệt trước nâng cấp', body='Nội dung kiểm thử, không dùng để đăng thật. ' * 6,
            angle='Kiểm tra giữ nguyên bản duyệt.', page_name='Page kiểm thử'))
        draft = self.room.save_draft(draft['id'], dict(revision=draft['revision'],
            checks={key: True for key in self.room.CHECKS}))
        draft = self.room.approve(draft['id'], draft['revision'])
        before = self.room.export(draft['id'])
        with self.room.connection() as conn:
            conn.execute('DROP TABLE custom_sources')
            conn.execute('PRAGMA user_version=2')
        self.room = Newsroom(self.room.data_dir)
        self.assertEqual(self.room.draft(draft['id']), draft)
        self.assertEqual(self.room.export(draft['id']), before)
        backups = list((self.room.data_dir / 'backups').glob('pre-v03-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 2)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        source = self.add()
        from newsroom.__main__ import restore
        destination = Path(self.temp.name) / 'restored'
        restore(self.room.backup(), destination)
        restored = Newsroom(destination)
        self.assertEqual(restored.draft(draft['id']), draft)
        self.assertEqual(restored.export(draft['id']), before)
        self.assertEqual(next(s for s in restored.collection_sources() if s['id'] == source['id']), source)

    def test_custom_web_paid_lane_passes_snapshot_but_requires_existing_explicit_gate(self):
        with patch('newsroom.subscriptions.read_public', return_value=(b'<html>News</html>', 'https://dev.to/news')):
            source = self.room.add_source(dict(self.data, kind='web', url='https://dev.to/news', prefix='/news/'))
        job = self.room.queue_browser(source['id'], 'Fixture requires interaction')
        html = '<main><h1>Fixture public technology announcement</h1><p>' + 'Fixture evidence only. ' * 20 + '</p></main>'
        config = {'max_jobs_per_day': 1, 'hermes_root': self.temp.name}
        with self.assertRaises(ValidationError):
            self.room.run_browser_job(job['id'], confirmed=False)
        with patch.object(self.room, 'browser_settings', return_value=(config, 'fixture-key')), \
                patch('newsroom.collection_service.tools_python', return_value='fixture-python'), \
                patch('newsroom.collection_service.run_worker', return_value={
                    'pages': [{'url': 'https://dev.to/news/fixture', 'html': html}]}) as worker:
            result = self.room.run_browser_job(job['id'], confirmed=True)
        self.assertEqual(result['added'], 1)
        self.assertEqual(worker.call_args.args[1]['source'], source)
        self.assertEqual(self.room.collection_jobs()[0]['status'], 'completed')
        self.assertEqual(self.room.drafts(), [])


class SubscriptionSafetyTests(unittest.TestCase):
    def test_pinned_https_ignores_proxy_and_blocks_redirect_outside_host(self):
        from newsroom.collection import fetch_bytes
        class FakeSocket:
            def __init__(self, raw):
                self.raw = raw
            def sendall(self, data):
                pass
            def makefile(self, mode):
                return io.BytesIO(self.raw)
            def close(self):
                pass
        reply = b'HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nfeed'
        source = {'url': 'https://dev.to/feed', 'kind': 'rss'}
        with patch('newsroom.collection.public_ip', return_value='1.1.1.1'), \
                patch('newsroom.collection.socket.create_connection', return_value=FakeSocket(reply)) as dial, \
                patch('newsroom.collection.ssl.create_default_context') as tls:
            tls.return_value.wrap_socket.side_effect = lambda raw, **kwargs: raw
            self.assertEqual(fetch_bytes(source['url'], source, return_url=True), (b'feed', source['url']))
            self.assertEqual(dial.call_args.args[0], ('1.1.1.1', 443))
            self.assertEqual(tls.return_value.wrap_socket.call_args.kwargs['server_hostname'], 'dev.to')
        redirect = b'HTTP/1.1 302 Found\r\nLocation: https://127.0.0.1/feed\r\nContent-Length: 0\r\n\r\n'
        with patch('newsroom.collection.public_ip', return_value='1.1.1.1'), \
                patch('newsroom.collection.socket.create_connection', return_value=FakeSocket(redirect)) as dial, \
                patch('newsroom.collection.ssl.create_default_context') as tls:
            tls.return_value.wrap_socket.side_effect = lambda raw, **kwargs: raw
            with self.assertRaises(FeedError):
                fetch_bytes(source['url'], source)
            self.assertEqual(dial.call_count, 1)

    def test_same_path_redirect_rechecks_robots_before_following(self):
        from newsroom.collection import fetch_bytes
        from unittest.mock import MagicMock
        response = MagicMock(status=302)
        response.getheader.return_value = 'https://dev.to/feed/'
        source = {'url': 'https://dev.to/feed', 'kind': 'rss'}
        with patch('newsroom.collection.public_ip', return_value='1.1.1.1'), \
                patch('newsroom.collection.http.client.HTTPSConnection.request'), \
                patch('newsroom.collection.http.client.HTTPSConnection.getresponse', return_value=response), \
                patch('newsroom.collection.check_robots', side_effect=AccessBlocked('Disallow trailing slash')) as robots:
            with self.assertRaises(AccessBlocked):
                fetch_bytes(source['url'], source, robots_on_redirect=True)
            robots.assert_called_once_with('https://dev.to/feed/', source)

    def test_public_read_checks_robots_and_uses_pinned_https(self):
        from newsroom.subscriptions import read_public
        with patch('newsroom.subscriptions.check_robots') as robots, \
                patch('newsroom.subscriptions.fetch_bytes', return_value=(FEED, 'https://dev.to/feed')) as fetch:
            self.assertEqual(read_public('https://dev.to/feed')[0], FEED)
            robots.assert_called_once()
            self.assertTrue(fetch.call_args.kwargs['return_url'])
        with patch('newsroom.collection.public_ip', side_effect=AccessBlocked('private DNS')):
            with self.assertRaises(FeedError):
                read_public('https://private.example/feed')

    def test_discovery_ignores_cross_host_http_and_unsafe_feed_links(self):
        from newsroom.subscriptions import discover_source
        raw = b'''<html><link rel="alternate" type="application/rss+xml" href="https://evil.example/feed">
        <link rel="alternate" type="application/rss+xml" href="http://dev.to/feed">
        <link rel="alternate" type="application/rss+xml" href="/feed/%2e%2e/private"></html>'''
        calls = []
        def read(url):
            calls.append(url)
            if len(calls) == 1:
                return raw, url
            raise FeedError('No feed')
        with patch('newsroom.subscriptions.read_public', side_effect=read):
            with self.assertRaises(FeedError):
                discover_source('https://dev.to/', 'auto', '')
        self.assertLessEqual(len(calls), 4)
        self.assertTrue(all(url.startswith('https://dev.to/') and '%' not in url for url in calls))

    def test_worker_validates_custom_snapshot_and_never_overrides_catalog(self):
        from newsroom.collection import worker_source
        custom = dict(id='custom-' + 'a' * 32, name='Example', kind='web',
                      url='https://example.org/news', site='https://example.org/news', prefix='/news/', custom=True)
        source = worker_source({'source_id': custom['id'], 'source': custom})
        self.assertEqual(source['prefix'], '/news/')
        for changed in (dict(custom, kind='api'), dict(custom, url='https://127.0.0.1/news'),
                        dict(custom, prefix='/news/../'), dict(custom, id='custom-x')):
            with self.subTest(changed=changed), self.assertRaises(FeedError):
                worker_source({'source_id': changed['id'], 'source': changed})
        self.assertEqual(worker_source({'source_id': 'typesafe', 'source': custom}), source_by_id('typesafe'))


if __name__ == '__main__':
    unittest.main()
