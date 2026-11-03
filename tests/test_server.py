import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from newsroom.server import MAX_BODY, make_server
from newsroom.service import Newsroom


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.room = Newsroom(Path(self.temp.name))
        self.server = make_server(self.room, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        body = json.dumps(data).encode() if data is not None else None
        conn.request(method, path, body, headers or {})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def session(self):
        status, headers, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        cookie = headers['Set-Cookie'].split(';')[0]
        status, _, body = self.request('GET', '/api/state', headers={'Cookie': cookie})
        token = json.loads(body)['csrf_token']
        return {'Cookie': cookie, 'X-CSRF-Token': token,
                'Origin': f'http://127.0.0.1:{self.port}', 'Content-Type': 'application/json'}

    def test_auth_and_csrf_fail_closed(self):
        self.assertEqual(self.request('GET', '/api/state')[0], 401)
        self.assertEqual(self.request('POST', '/api/articles/import', {})[0], 401)
        headers = self.session()
        without_token = dict(headers)
        without_token.pop('X-CSRF-Token')
        self.assertEqual(self.request('POST', '/api/articles/import', {}, without_token)[0], 403)
        headers['Origin'] = 'https://evil.example'
        self.assertEqual(self.request('POST', '/api/articles/import', {}, headers)[0], 403)

    def test_host_and_static_traversal(self):
        self.assertEqual(self.request('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('GET', '/static/source-warnings.js')[0], 200)
        self.assertEqual(self.request('GET', '/static/request-size.js')[0], 200)
        self.assertEqual(self.request('GET', '/static/inbox-utils.js')[0], 200)
        self.assertEqual(self.request('GET', '/static/../service.py')[0], 404)

    def test_security_headers_and_import_roundtrip(self):
        headers = self.session()
        status, response_headers, body = self.request('GET', '/', headers=headers)
        self.assertIn('Content-Security-Policy', response_headers)
        self.assertIn(b'lang="vi"', body)
        self.assertNotIn('Access-Control-Allow-Origin', response_headers)
        status, _, body = self.request('POST', '/api/articles/import', {
            'title': 'Một nguồn tin thử nghiệm', 'url': 'https://example.com/safe',
            'summary': '<script>untrusted()</script>',
        }, headers)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['id'])
        self.assertEqual(self.request('GET', '/api/state', headers=headers)[0], 200)

    def test_home_retains_editor_and_safe_external_link(self):
        status, headers, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('Content-Security-Policy', headers)
        self.assertIn(b'id="view-bulletins"', body)
        self.assertIn(b'id="copy-packet"', body)
        self.assertIn(b'href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer"', body)
        page = body.decode('utf-8')
        self.assertIn('Bản 0.4 đang phát triển', page)
        self.assertIn('Bạn có thể tự viết hoặc chuyển gói tư liệu sang công cụ AI', page)
        self.assertIn('Facebook, Threads hoặc X', page)
        self.assertIn('Ứng dụng không kết nối tài khoản hay tự đăng.', page)

    def test_malformed_and_oversize_requests(self):
        headers = self.session()
        self.assertEqual(self.request('POST', '/api/articles/import', [], headers)[0], 400)
        self.assertEqual(self.request('POST', '/api/articles/import', {'summary': 'x' * 130_000}, headers)[0], 413)
        unicode_token = dict(headers, **{'X-CSRF-Token': '\u00e9'})
        self.assertEqual(self.request('POST', '/api/backup', {}, unicode_token)[0], 403)

    def test_bulletin_request_utf8_size_boundary_over_http(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin kiểm tra giới hạn',
            'url': 'https://example.com/byte-boundary', 'summary': 'Nguồn thử.'})
        payload = {'article_ids': [article['id']], 'title': 'Bản tin tiếng Việt 😀', 'padding': 'é'}
        encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        payload['padding'] += 'x' * (MAX_BODY - len(encode(payload)))
        exact = encode(payload)
        self.assertEqual(len(exact), MAX_BODY)

        def post(body):
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
            try:
                conn.request('POST', '/api/bulletins', body, headers)
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()

        status, body = post(exact)
        self.assertEqual(status, 201)
        created = json.loads(body)
        self.assertEqual(created['title'], payload['title'])
        self.assertEqual([item['article_id'] for item in created['items']], [article['id']])
        payload['padding'] += 'x'
        over = encode(payload)
        self.assertEqual(len(over), MAX_BODY + 1)
        status, _ = post(over)
        self.assertEqual(status, 413)
        self.assertEqual(self.room.bulletin(created['id']), created)
        with self.room.connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM bulletins').fetchone()[0], 1)

    def test_json_rejects_unpaired_surrogates_without_saving_and_accepts_emoji(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin fixture Unicode',
            'url': 'https://example.com/unicode', 'summary': 'Nguồn minh họa.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        for platform in ('x', 'threads', 'facebook'):
            with self.subTest(platform=platform):
                variant = self.room.create_variant(bulletin['id'], {
                    'bulletin_revision': bulletin['revision'], 'platform': platform, 'account_label': 'Kênh thử'})
                path = f"/api/variants/{variant['id']}/save"
                for invalid in ('\ud800', '\udfff'):
                    segment = {'text': 'Lỗi ' + invalid, 'item_ids': [bulletin['items'][0]['id']]}
                    status, _, body = self.request('POST', path, {'revision': variant['revision'], 'segments': [segment]}, headers)
                    self.assertEqual(status, 400)
                    self.assertIn('Unicode không hợp lệ', json.loads(body)['error'])
                    self.assertEqual(self.room.variant(variant['id']), variant)
                segment['text'] = 'Emoji hợp lệ 😀'
                self.assertEqual(self.request('POST', path, {'revision': variant['revision'], 'segments': [segment]}, headers)[0], 200)

    def test_no_publish_or_ai_integration_endpoint(self):
        headers = self.session()
        for endpoint in ('/api/ai', '/api/facebook/publish', '/api/login/chatgpt'):
            self.assertEqual(self.request('POST', endpoint, {}, headers)[0], 404)

    def test_bulletin_and_variant_routes_enforce_session_and_support_preview_split(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin trong fixture HTTP',
            'url': 'https://example.com/fixture', 'summary': 'Nguồn minh họa.'})
        payload = {'article_ids': [article['id']], 'title': 'Bản tin thử'}
        self.assertEqual(self.request('POST', '/api/bulletins', payload)[0], 401)
        without_token = dict(headers)
        without_token.pop('X-CSRF-Token')
        self.assertEqual(self.request('POST', '/api/bulletins', payload, without_token)[0], 403)
        status, _, body = self.request('POST', '/api/bulletins', payload, headers)
        self.assertEqual(status, 201)
        bulletin = json.loads(body)
        item_id = bulletin['items'][0]['id']
        status, _, body = self.request('POST', f"/api/bulletins/{bulletin['id']}/variants", {
            'bulletin_revision': bulletin['revision'], 'platform': 'x', 'account_label': 'Kênh thử'}, headers)
        self.assertEqual(status, 200)
        variant = json.loads(body)
        segment = {'text': ('Một câu minh họa. ' * 30).strip(), 'item_ids': [item_id]}
        path = f"/api/variants/{variant['id']}"
        self.assertEqual(self.request('POST', path + '/split', {'revision': variant['revision'],
                                                                'segments': [segment]}, without_token)[0], 403)
        status, _, body = self.request('POST', path + '/split', {'revision': variant['revision'],
                                                                  'segments': [segment]}, headers)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertGreater(len(result['segments']), 1)
        self.assertTrue(result['preview']['valid'])
        self.assertTrue(all(post['urls'] == [article['url']] for post in result['preview']['posts']))
        self.assertEqual(self.request('POST', path + '/split', {'revision': 999, 'segments': [segment]}, headers)[0], 409)
        self.assertEqual(self.request('GET', path + '/export', headers=headers)[0], 400)
        self.assertEqual(self.request('POST', path + '/publications', {'revision': 1,
            'position': 0, 'url': 'https://x.com/test/status/123', 'idempotency_key': 'test_key_123'}, headers)[0], 400)

    def test_copy_legacy_endpoint_requires_csrf_and_revision(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin gốc', 'url': 'https://example.com/legacy', 'summary': ''})
        draft = self.room.create_draft(article['id'])
        path = f"/api/drafts/{draft['id']}/copy-bulletin"
        no_token = dict(headers)
        no_token.pop('X-CSRF-Token')
        self.assertEqual(self.request('POST', path, {'revision': draft['revision']}, no_token)[0], 403)
        self.assertEqual(self.request('POST', path, {'revision': 0}, headers)[0], 409)
        status, _, body = self.request('POST', path, {'revision': draft['revision']}, headers)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(self.room.variant(result['variant_id'])['status'], 'draft')
        self.assertEqual(self.room.draft(draft['id']), draft)

    def test_collection_endpoints_require_session_csrf_and_confirmation(self):
        path = '/api/collection/sources/typesafe'
        self.assertEqual(self.request('POST', path, {'enabled': True, 'confirmed': True})[0], 401)
        headers = self.session()
        bad = dict(headers)
        bad.pop('X-CSRF-Token')
        self.assertEqual(self.request('POST', path, {'enabled': True, 'confirmed': True}, bad)[0], 403)
        self.assertEqual(self.request('POST', path, {'enabled': True}, headers)[0], 400)
        self.assertEqual(self.request('POST', path, {'enabled': True, 'confirmed': True}, headers)[0], 200)
        self.assertEqual(self.request('POST', '/api/collection/sources/localhost',
                                      {'enabled': True, 'confirmed': True}, headers)[0], 400)
        job = self.room.queue_browser('typesafe', 'fixture')
        with patch('newsroom.collection_service.run_worker') as worker:
            self.assertEqual(self.request('POST', f"/api/collection/jobs/{job['id']}/run", {}, headers)[0], 400)
            self.assertEqual(self.request('POST', f"/api/collection/jobs/{job['id']}/run", {'confirmed': True}, headers)[0], 400)
            worker.assert_not_called()

    def test_browser_job_preflight_returns_error_not_false_started(self):
        headers = self.session()
        self.room.configure_source('typesafe', {'enabled': True, 'confirmed': True})
        config = {'max_jobs_per_day': 1, 'hermes_root': self.temp.name}
        with patch.object(self.room, 'browser_settings', return_value=(config, 'fixture-key')), \
                patch('newsroom.collection_service.run_worker') as worker:
            status, _, _ = self.request('POST', '/api/collection/jobs/99999/run', {'confirmed': True}, headers)
            self.assertEqual(status, 400)
            self.assertFalse(self.server.job_lock.locked())
            job = self.room.queue_browser('typesafe', 'fixture')
            with self.room.connection() as conn:
                conn.execute('INSERT INTO collection_attempts(job_id,started_at) VALUES (?,datetime(\'now\'))', (job['id'],))
            status, _, body = self.request('POST', f"/api/collection/jobs/{job['id']}/run", {'confirmed': True}, headers)
            self.assertEqual(status, 400)
            self.assertIn('24', json.loads(body)['error'])
            self.assertFalse(self.server.job_lock.locked())
            worker.assert_not_called()

    def test_custom_source_endpoint_adds_to_sources_not_articles_and_handles_duplicate(self):
        headers = self.session()
        data = dict(name='DEV Community', url='https://dev.to/feed', kind='rss', confirmed=True)
        feed = b'<rss version="2.0"><channel><title>DEV</title></channel></rss>'
        with patch('newsroom.subscriptions.read_public', return_value=(feed, data['url'])):
            status, _, body = self.request('POST', '/api/collection/sources', data, headers)
        self.assertEqual(status, 201)
        source = json.loads(body)
        status, _, body = self.request('GET', '/api/state', headers=headers)
        state = json.loads(body)
        self.assertTrue(state['features']['custom_sources'])
        self.assertEqual(len(state['sources']), 8)
        self.assertEqual(state['sources'][-1]['id'], source['id'])
        self.assertEqual(state['articles'], [])
        with patch('newsroom.subscriptions.read_public') as read:
            self.assertEqual(self.request('POST', '/api/collection/sources', data, headers)[0], 400)
            read.assert_not_called()
        self.assertFalse(self.server.job_lock.locked())
        self.assertEqual(self.request('POST', '/api/collection/sources/' + source['id'],
                                      {'enabled': False}, headers)[0], 200)

    def test_custom_source_requires_auth_confirmation_and_free_collection_slot(self):
        data = dict(name='DEV Community', url='https://dev.to/', kind='auto', confirmed=True)
        headers = self.session()
        with patch('newsroom.subscriptions.read_public') as read:
            self.assertEqual(self.request('POST', '/api/collection/sources', data)[0], 401)
            bad = dict(headers)
            bad.pop('X-CSRF-Token')
            self.assertEqual(self.request('POST', '/api/collection/sources', data, bad)[0], 403)
            self.assertEqual(self.request('POST', '/api/collection/sources', dict(data, confirmed=False), headers)[0], 400)
            self.assertFalse(self.server.job_lock.locked())
            self.server.job_lock.acquire()
            try:
                self.assertEqual(self.request('POST', '/api/collection/sources', data, headers)[0], 400)
                self.assertTrue(self.server.job_lock.locked())
            finally:
                self.server.job_lock.release()
            read.assert_not_called()

    def test_source_and_manual_article_buttons_have_distinct_labels(self):
        status, _, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        html = body.decode('utf-8')
        self.assertIn('Thêm nguồn theo dõi', html)
        self.assertIn('Nhập bài thủ công', html)
        self.assertNotIn('＋ Nhập nguồn', html)


if __name__ == '__main__':
    unittest.main()
