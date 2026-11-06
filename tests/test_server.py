import http.client
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from newsroom.server import MAX_BODY, Handler, make_server
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

    def test_packet_revision_matches_the_bulletin_inside_http_response(self):
        from newsroom.bulletins import PACKET_PREFIX, PACKET_SUFFIX
        headers = self.session()
        article = self.room.import_article({'title': 'Nguồn giả',
            'url': 'https://example.com/packet-revision', 'summary': 'Tư liệu thử.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']], 'title': 'Bản đầu'})
        for title in ('Bản đầu', 'Bản sửa'):
            if title != bulletin['title']:
                bulletin = self.room.save_bulletin(bulletin['id'], {'revision': bulletin['revision'], 'title': title})
            status, _, body = self.request('GET', f"/api/bulletins/{bulletin['id']}/packet", headers=headers)
            self.assertEqual(status, 200)
            response = json.loads(body)
            self.assertTrue(response['text'].startswith(PACKET_PREFIX))
            self.assertTrue(response['text'].endswith(PACKET_SUFFIX))
            data = json.loads(response['text'][len(PACKET_PREFIX):-len(PACKET_SUFFIX)])
            self.assertEqual(response['bulletin_revision'], data['revision'])
            self.assertEqual((data['revision'], data['title']), (bulletin['revision'], title))

    def test_auth_and_csrf_fail_closed(self):
        self.assertEqual(self.request('GET', '/api/state')[0], 401)
        self.assertEqual(self.request('POST', '/api/articles/import', {})[0], 401)
        headers = self.session()
        without_token = dict(headers)
        without_token.pop('X-CSRF-Token')
        self.assertEqual(self.request('POST', '/api/articles/import', {}, without_token)[0], 403)
        headers['Origin'] = 'https://evil.example'
        self.assertEqual(self.request('POST', '/api/articles/import', {}, headers)[0], 403)

    def test_short_request_body_is_rejected_before_mutation(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử độ dài',
            'url': 'https://example.com/short-body', 'summary': 'Dữ liệu giả.'})
        body = json.dumps({'article_ids': [article['id']], 'title': 'Bản tin thử'}).encode('utf-8')
        request_headers = {'Host': f'127.0.0.1:{self.port}', **headers,
                           'Content-Length': str(len(body) + 1)}
        request = ('POST /api/bulletins HTTP/1.1\r\n' +
                   ''.join(f'{name}: {value}\r\n' for name, value in request_headers.items()) +
                   '\r\n').encode('ascii') + body
        with socket.create_connection(('127.0.0.1', self.port), timeout=5) as client:
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)
            response = http.client.HTTPResponse(client)
            response.begin()
            self.assertEqual(response.status, 400)
            self.assertIn('error', json.loads(response.read()))
        self.assertEqual(self.room.bulletins(), [])
        status, _, response_body = self.request('POST', '/api/bulletins',
            {'article_ids': [article['id']], 'title': 'Bản tin thử'}, headers)
        self.assertEqual(status, 201, response_body)
        self.assertEqual(len(self.room.bulletins()), 1)

    def test_bulletin_archive_http_is_reversible_and_checks_revisions(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử lưu trữ',
            'url': 'https://example.com/archive-http', 'summary': 'Dữ liệu giả.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']], 'title': 'Bản tin thử'})
        path = f"/api/bulletins/{bulletin['id']}/archive"
        payload = {'revision': bulletin['revision'], 'archive_revision': 0, 'archived': True}
        self.assertEqual(self.request('POST', path, payload)[0], 401)
        missing_csrf = dict(headers)
        missing_csrf.pop('X-CSRF-Token')
        self.assertEqual(self.request('POST', path, payload, missing_csrf)[0], 403)
        for invalid in (None, 0, 'true', [], {}):
            with self.subTest(invalid=invalid):
                status, _, _ = self.request('POST', path, {**payload, 'archived': invalid}, headers)
                self.assertEqual(status, 400)
                self.assertFalse(self.room.bulletin(bulletin['id'])['archived'])
        for invalid in (None, False, -1, '0', [], {}):
            with self.subTest(archive_revision=invalid):
                status, _, _ = self.request('POST', path, {**payload, 'archive_revision': invalid}, headers)
                self.assertEqual(status, 400)
                self.assertFalse(self.room.bulletin(bulletin['id'])['archived'])
        for invalid in (None, False, '1', [], {}):
            with self.subTest(revision=invalid):
                status, _, _ = self.request('POST', path, {**payload, 'revision': invalid}, headers)
                self.assertEqual(status, 409)
                self.assertFalse(self.room.bulletin(bulletin['id'])['archived'])
        status, _, body = self.request('POST', path, payload, headers)
        self.assertEqual(status, 200, body)
        archived = json.loads(body)
        self.assertTrue(archived['archived'])
        self.assertGreater(archived['archive_revision'], 0)
        status, _, body = self.request('GET', '/api/bulletins', headers=headers)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)[0]['archived'])
        status, _, _ = self.request('POST', path, {**payload, 'archived': False}, headers)
        self.assertEqual(status, 409)
        status, _, body = self.request('POST', path, {**payload, 'archive_revision': archived['archive_revision'],
                                                     'archived': False}, headers)
        self.assertEqual(status, 200, body)
        self.assertFalse(json.loads(body)['archived'])

    def test_invalid_multichannel_field_types_do_not_change_saved_data(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử kiểu dữ liệu',
            'url': 'https://example.com/http-bad-types', 'summary': 'Dữ liệu giả.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']], 'title': 'Bản tin thử'})
        item = bulletin['items'][0]
        variant = self.room.create_variant(bulletin['id'], {
            'bulletin_revision': bulletin['revision'], 'platform': 'x'})
        before_bulletin = self.room.bulletin(bulletin['id'])
        before_variant = self.room.variant(variant['id'])
        before_history = self.room.bulletin_history(bulletin['id'])
        invalid = (None, 7, 'sai kiểu', {})
        cases = [
            ('/api/bulletins', {'article_ids': [article['id']]}, 'article_ids', invalid + (False, [])),
            (f"/api/bulletins/{bulletin['id']}/save", {'revision': bulletin['revision']},
             'item_ids', invalid + (False, [])),
            (f"/api/bulletins/{bulletin['id']}/items/{item['id']}/save",
             {'bulletin_revision': bulletin['revision'], 'revision': item['revision']}, 'verified', invalid + ([],)),
            (f"/api/bulletins/{bulletin['id']}/items/{item['id']}/save",
             {'bulletin_revision': bulletin['revision'], 'revision': item['revision']}, 'claims', invalid + (False,)),
            (f"/api/variants/{variant['id']}/save", {'revision': variant['revision']},
             'segments', invalid + (False, [])),
            (f"/api/variants/{variant['id']}/preview", {}, 'segments', invalid + (False, [])),
        ]
        for path, base, field, invalid_values in cases:
            for value in invalid_values:
                with self.subTest(path=path, field=field, value=value):
                    status, _, body = self.request('POST', path, {**base, field: value}, headers)
                    self.assertEqual(status, 400, body)
                    self.assertIn('error', json.loads(body))
        self.assertEqual(self.room.bulletin(bulletin['id']), before_bulletin)
        self.assertEqual(self.room.variant(variant['id']), before_variant)
        self.assertEqual(self.room.bulletin_history(bulletin['id']), before_history)
        self.assertEqual(len(self.room.bulletins()), 1)

    def test_publication_fields_reject_invalid_input_without_partial_writes(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin giả kiểm tra nhật ký',
            'url': 'https://example.com/publication-validation', 'summary': 'Nguồn giả lập.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
            'body': 'Thông tin giả.', 'verification_note': 'Đối chiếu nguồn giả lập trên fixture.',
            'claims': [{'text': 'Dữ liệu giả', 'evidence': 'Fixture', 'checked': True}]})
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'], 'verified': True,
            'claims': [{**item['claims'][0], 'checked': True}]})
        variant = self.room.create_variant(bulletin['id'], {'bulletin_revision': bulletin['revision'],
            'platform': 'x', 'account_label': 'Kênh giả'})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
            'segments': [{'text': 'Bản tin giả.', 'item_ids': [item['id']]}]})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
            'checks': {key: True for key in ('sources', 'facts', 'original', 'rights', 'claims')}})
        variant = self.room.approve_variant(variant['id'], {'revision': variant['revision']})
        record_path = f"/api/variants/{variant['id']}/publications"
        record = {'revision': variant['revision'], 'position': 0,
                  'url': 'https://x.com/fixture/status/441', 'idempotency_key': 'invalid_fields_441'}

        def check_invalid(path, payload, status, expected_variant, expected_publications, expected_history):
            actual, _, body = self.request('POST', path, payload, headers)
            self.assertEqual(actual, status, body)
            self.assertIn('error', json.loads(body))
            self.assertEqual(self.room.bulletin(bulletin['id']), bulletin)
            self.assertEqual(self.room.variant(variant['id']), expected_variant)
            self.assertEqual(self.room.publications(variant['id']), expected_publications)
            self.assertEqual(self.room.bulletin_history(bulletin['id']), expected_history)
            active = sum(entry['active'] for entry in expected_publications)
            self.assertEqual(self.room.bulletin_stats(), {'bulletins': 1, 'variants': 1,
                'recorded_bulletins': int(active > 0), 'recorded_posts': active})

        before_history = self.room.bulletin_history(bulletin['id'])
        record_cases = {
            'position': (None, True, -1, 1, 1.5, '0', [], {}),
            'idempotency_key': (None, True, 1, 'short', 'x' * 101, 'invalid:key'),
            'url': (None, True, [], {}, '', 'https://example.com/not-x', 'https://x.com/account',
                    'https://@x.com/fixture/status/441', 'https://:@x.com/fixture/status/441'),
            'reported_at': (True, [], {}, 'không phải ngày', '2026-11-06T10:00:00'),
        }
        for field, values in record_cases.items():
            for value in values:
                with self.subTest(route='record', field=field, value=value):
                    check_invalid(record_path, {**record, field: value}, 400, variant, [], before_history)
        for value in (None, True, '1', variant['revision'] - 1):
            with self.subTest(route='record', field='revision', value=value):
                check_invalid(record_path, {**record, 'revision': value}, 409, variant, [], before_history)

        status, _, body = self.request('POST', record_path, record, headers)
        self.assertEqual(status, 200, body)
        publication = json.loads(body)
        current = self.room.variant(variant['id'])
        publications = self.room.publications(variant['id'])
        history = self.room.bulletin_history(bulletin['id'])
        correction_path = f"/api/publications/{publication['id']}/corrections"
        correction = {'revision': current['revision'], 'reason': 'Sửa liên kết giả lập',
                      'url': 'https://x.com/fixture/status/442'}
        for field, values in {
            'reason': (None, False, [], {}, '', 'ab'),
            'url': (None, False, [], {}, 'https://example.com/not-x', record['url']),
        }.items():
            for value in values:
                with self.subTest(route='correction', field=field, value=value):
                    check_invalid(correction_path, {**correction, field: value}, 400, current, publications, history)
        for value in (None, True, '1', current['revision'] - 1):
            with self.subTest(route='correction', field='revision', value=value):
                check_invalid(correction_path, {**correction, 'revision': value}, 409, current, publications, history)

        metric_path = f"/api/publications/{publication['id']}/metrics"
        metric = {'observed_at': '2026-11-06T10:00:00+07:00', 'idempotency_key': 'invalid_metrics_441'}
        for field in ('views', 'likes', 'saves', 'shares', 'followers', 'minutes', 'replies', 'reposts', 'quotes'):
            for value in (True, -1, 1.5, 1000000001, '0', [], {}):
                with self.subTest(route='metrics', field=field, value=value):
                    check_invalid(metric_path, {**metric, field: value}, 400, current, publications, history)
        for field, values in {
            'observed_at': (None, '', True, [], {}, 'không phải ngày', '2026-11-06T10:00:00'),
            'idempotency_key': (True, 1, [], {}, 'short', 'x' * 101, 'invalid:key'),
            'note': (None, False, [], {}, 'x' * 1001),
        }.items():
            for value in values:
                with self.subTest(route='metrics', field=field, value=value):
                    check_invalid(metric_path, {**metric, field: value}, 400, current, publications, history)

    def test_threads_encoded_shortcode_conflicts_over_http_without_rewriting_history(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử liên kết Threads',
            'url': 'https://example.com/threads-http-identity', 'summary': 'Nguồn giả.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
            'body': 'Nội dung thử.', 'verification_note': 'Đối chiếu nguồn giả trên kho kiểm thử.',
            'claims': [{'text': 'Dữ liệu giả', 'evidence': 'Fixture', 'checked': True}]})
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'], 'verified': True,
            'claims': [{**item['claims'][0], 'checked': True}]})
        variants = []
        for account in ('Kênh giả 1', 'Kênh giả 2'):
            variant = self.room.create_variant(bulletin['id'], {'bulletin_revision': bulletin['revision'],
                'platform': 'threads', 'account_label': account})
            variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
                'segments': [{'text': 'Nội dung thử.', 'item_ids': [item['id']]}]})
            variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
                'checks': {key: True for key in ('sources', 'facts', 'original', 'rights', 'claims')}})
            variants.append(self.room.approve_variant(variant['id'], {'revision': variant['revision']}))
        first, second = variants
        original = self.room.record_publication(first['id'], {'revision': first['revision'], 'position': 0,
            'url': 'https://threads.com/@fixture/post/%41bc%5F12', 'idempotency_key': 'encoded_http_first'})
        before = self.room.publications(first['id'])
        self.assertIn('%41bc%5F12', before[0]['url'])
        data = {'revision': second['revision'], 'position': 0, 'url': 'https://threads.net/t/Abc_12',
                'idempotency_key': 'encoded_http_second'}
        status, _, body = self.request('POST', f"/api/variants/{second['id']}/publications", data, headers)
        self.assertEqual(status, 409, body)
        self.assertEqual(json.loads(body)['target'], {'kind': 'publication', 'bulletin_id': bulletin['id'],
            'variant_id': first['id'], 'publication_id': original['id'], 'position': 0})
        current = self.room.variant(first['id'])
        status, _, body = self.request('POST', f"/api/publications/{original['id']}/corrections", {
            'revision': current['revision'], 'reason': 'Kiểm tra liên kết', 'url': data['url']}, headers)
        self.assertEqual(status, 400, body)
        self.assertEqual(self.room.publications(first['id']), before)
        self.assertEqual(self.room.publications(second['id']), [])
        self.assertEqual(self.room.variant(second['id']), second)

    def test_variant_platform_wrong_json_types_are_rejected_without_writes(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử kiểu nền tảng',
            'url': 'https://example.com/platform-type', 'summary': 'Dữ liệu giả.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        path = f"/api/bulletins/{bulletin['id']}/variants"
        for value in ([], {}, None, True, 1, 'invalid'):
            with self.subTest(platform=value):
                status, _, body = self.request('POST', path, {
                    'bulletin_revision': bulletin['revision'], 'platform': value,
                    'account_label': 'Kênh thử'}, headers)
                self.assertEqual(status, 400, body)
                self.assertIn('error', json.loads(body))
                self.assertEqual(self.room.variants(bulletin['id']), [])

    def test_invalid_source_selection_is_rejected_over_http_without_writes(self):
        headers = self.session()
        first = self.room.import_article({'title': 'Tin chọn nguồn 1',
            'url': 'https://example.com/http-source-1', 'summary': 'Nguồn giả một.'})
        second = self.room.import_article({'title': 'Tin chọn nguồn 2',
            'url': 'https://example.com/http-source-2', 'summary': 'Nguồn giả hai.'})
        draft = self.room.create_draft(first['id'])
        for selection in ({str(second['id']): [second['url']]}, {str(first['id']): None}):
            with self.subTest(selection=selection):
                status, _, body = self.request('POST', '/api/bulletins',
                    {'article_ids': [first['id']], 'source_selection': selection}, headers)
                self.assertEqual(status, 400, body)
                self.assertIn('error', json.loads(body))
                self.assertEqual(self.room.bulletins(), [])
        bulletin = self.room.create_bulletin({'article_ids': [first['id']]})
        before_history = self.room.bulletin_history(bulletin['id'])
        status, _, body = self.request('POST', f"/api/bulletins/{bulletin['id']}/items", {
            'revision': bulletin['revision'], 'article_id': second['id'], 'source_selection': None}, headers)
        self.assertEqual(status, 400, body)
        self.assertEqual(self.room.bulletin(bulletin['id']), bulletin)
        self.assertEqual(self.room.bulletin_history(bulletin['id']), before_history)
        status, _, body = self.request('POST', f"/api/drafts/{draft['id']}/copy-bulletin", {
            'revision': draft['revision'], 'source_selection': None}, headers)
        self.assertEqual(status, 400, body)
        self.assertEqual(len(self.room.bulletins()), 1)
        self.assertEqual(self.room.draft(draft['id']), draft)

    def test_preview_and_split_response_contract_over_http(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử preview',
            'url': 'https://example.com/preview-contract', 'summary': 'Nguồn giả lập.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        variant = self.room.create_variant(bulletin['id'], {'bulletin_revision': bulletin['revision'],
            'platform': 'threads', 'account_label': 'Kênh thử'})
        path = f"/api/variants/{variant['id']}"
        segments = [{'text': 'Một câu giả lập.', 'item_ids': [bulletin['items'][0]['id']]}]
        history_before = self.room.bulletin_history(bulletin['id'])

        status, _, body = self.request('POST', path + '/preview', {'segments': segments}, headers)
        self.assertEqual(status, 200, body)
        preview = json.loads(body)
        renderer_fields = {'platform', 'policy_version', 'renderer_version', 'posts', 'valid', 'warning'}
        context_fields = {'needs_update', 'bulletin_revision', 'omitted_item_ids'}
        self.assertEqual(set(preview), renderer_fields | context_fields)
        self.assertEqual(preview['bulletin_revision'], bulletin['revision'])
        self.assertFalse(preview['needs_update'])
        self.assertEqual(preview['omitted_item_ids'], [])
        self.assertEqual(preview['posts'][0]['body'], segments[0]['text'])

        status, _, body = self.request('POST', path + '/split', {
            'revision': variant['revision'], 'expected_bulletin_revision': bulletin['revision'],
            'segments': segments}, headers)
        self.assertEqual(status, 200, body)
        split = json.loads(body)
        self.assertEqual(set(split), {'segments', 'preview'})
        self.assertEqual(set(split['preview']), renderer_fields)
        self.assertEqual(split['preview'], {key: preview[key] for key in renderer_fields})
        self.assertEqual(split['segments'][0]['text'], segments[0]['text'])
        self.assertEqual(self.room.variant(variant['id']), variant)
        self.assertEqual(self.room.bulletin(bulletin['id']), bulletin)
        self.assertEqual(self.room.bulletin_history(bulletin['id']), history_before)

    def test_variant_save_contract_over_http(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử hợp đồng lưu',
            'url': 'https://example.com/save-contract', 'summary': 'Nguồn giả lập.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        item = bulletin['items'][0]
        variant = self.room.create_variant(bulletin['id'], {'bulletin_revision': bulletin['revision'],
            'platform': 'threads', 'account_label': 'Kênh thử'})
        path = f"/api/variants/{variant['id']}/save"
        checks = {key: True for key in ('sources', 'facts', 'original', 'rights', 'claims')}
        segment = {'text': 'Đoạn thử.', 'item_ids': [item['id']]}

        status, _, body = self.request('POST', path, {'revision': variant['revision'],
            'segments': [segment], 'checks': checks}, headers)
        self.assertEqual(status, 200, body)
        saved = json.loads(body)
        self.assertTrue(all(value is False for value in saved['checks'].values()))

        status, _, body = self.request('POST', path, {'revision': saved['revision'], 'checks': checks}, headers)
        self.assertEqual(status, 200, body)
        checked = json.loads(body)
        self.assertEqual(checked['checks'], checks)
        status, _, body = self.request('POST', path, {'revision': checked['revision']}, headers)
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body), checked)

        for sources in ([], ['nguon-khong-thuoc-muc']):
            with self.subTest(sources=sources):
                status, _, body = self.request('POST', path, {'revision': checked['revision'],
                    'segments': [{**segment, 'source_ids': sources}]}, headers)
                self.assertEqual(status, 400, body)
                self.assertEqual(self.room.variant(variant['id']), checked)
        status, _, body = self.request('POST', path, {'revision': saved['revision'],
            'segments': [segment]}, headers)
        self.assertEqual(status, 409, body)
        self.assertEqual(self.room.variant(variant['id']), checked)

    def test_http_approval_blocks_unresolved_item_note_until_reviewed(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin kiểm tra duyệt',
            'url': 'https://example.com/policy-v4', 'summary': 'Nguồn giả.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
            'body': 'Bản tin giả đã biên tập.', 'verification_note': 'Nguồn [CHƯA XÁC MINH] cần kiểm tra.',
            'claims': [{'text': 'Khẳng định thử', 'evidence': 'Nguồn giả', 'checked': False}]})
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'], 'verified': True,
            'claims': [{**item['claims'][0], 'checked': True}]})
        variant = self.room.create_variant(bulletin['id'], {
            'bulletin_revision': bulletin['revision'], 'platform': 'facebook', 'account_label': 'Trang thử'})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
            'segments': [{'text': 'Nội dung giả.', 'item_ids': [item['id']]}]})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
            'checks': {key: True for key in ('sources', 'facts', 'original', 'rights', 'claims')}})
        path = f"/api/variants/{variant['id']}"
        status, _, body = self.request('POST', path + '/approve', {'revision': variant['revision']}, headers)
        self.assertEqual(status, 400, body)
        self.assertIn('ghi chú kiểm chứng của mục 1', json.loads(body)['error'])
        self.assertEqual(self.room.variant(variant['id']), variant)
        self.assertEqual(self.request('GET', path + '/export', headers=headers)[0], 400)

        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
            'verification_note': 'Đã kiểm tra nguồn giả phù hợp.'})
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'], 'verified': True,
            'claims': [{**item['claims'][0], 'checked': True}]})
        variant = self.room.variant(variant['id'])
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'], 'adopt_bulletin_revision': True})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
            'checks': {key: True for key in ('sources', 'facts', 'original', 'rights', 'claims')}})
        status, _, body = self.request('POST', path + '/approve', {'revision': variant['revision']}, headers)
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)['status'], 'approved')
        self.assertEqual(self.request('GET', path + '/export', headers=headers)[0], 200)

    def test_variant_actions_reject_outdated_displayed_bulletin_over_http(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin giả kiểm tra thẻ cũ',
            'url': 'https://example.com/stale-actions', 'summary': 'Nguồn giả.'})
        original = self.room.create_bulletin({'article_ids': [article['id']]})
        variant = self.room.create_variant(original['id'], {'bulletin_revision': original['revision'],
            'platform': 'x', 'account_label': 'Kênh giả'})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
            'segments': [{'text': 'Một câu tin giả.', 'item_ids': [original['items'][0]['id']]}]})
        updated = self.room.save_bulletin(original['id'], {'revision': original['revision'], 'title': 'Đã đổi'})
        current = self.room.variant(variant['id'])
        current = self.room.save_variant(current['id'], {'revision': current['revision'],
            'expected_bulletin_revision': updated['revision'], 'adopt_bulletin_revision': True})
        path = f"/api/variants/{current['id']}"
        status, _, body = self.request('POST', path + '/preview', {}, headers)
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)['bulletin_revision'], updated['revision'])
        self.assertFalse(json.loads(body)['needs_update'])
        history = self.room.bulletin_history(original['id'])
        variants = self.room.variants(original['id'])
        payload = {'revision': current['revision'], 'expected_bulletin_revision': original['revision']}
        for action in ('split', 'clone', 'approve'):
            with self.subTest(action=action):
                status, _, body = self.request('POST', path + '/' + action, payload, headers)
                self.assertEqual(status, 409, body)
                self.assertEqual(self.room.variants(original['id']), variants)
                self.assertEqual(self.room.bulletin_history(original['id']), history)
        payload['expected_bulletin_revision'] = updated['revision']
        self.assertEqual(self.request('POST', path + '/split', payload, headers)[0], 200)
        self.assertEqual(self.request('POST', path + '/approve', payload, headers)[0], 400)
        self.assertEqual(self.request('POST', path + '/clone', payload, headers)[0], 200)

    def test_variant_save_rejects_outdated_displayed_bulletin_over_http(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử bản tin cũ',
            'url': 'https://example.com/stale-display', 'summary': 'Nguồn giả.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        variant = self.room.create_variant(bulletin['id'], {
            'bulletin_revision': bulletin['revision'], 'platform': 'x', 'account_label': 'Kênh giả'})
        updated = self.room.save_bulletin(bulletin['id'], {'revision': bulletin['revision'], 'title': 'Đã sửa'})
        current = self.room.variant(variant['id'])
        payload = {'revision': current['revision'], 'expected_bulletin_revision': bulletin['revision'],
                   'adopt_bulletin_revision': True,
                   'segments': [{'text': 'Nội dung đang soạn', 'item_ids': [bulletin['items'][0]['id']]}]}
        path = f"/api/variants/{variant['id']}/save"
        status, _, body = self.request('POST', path, payload, headers)
        self.assertEqual(status, 409, body)
        self.assertIn('Bản tin', json.loads(body)['error'])
        self.assertEqual(self.room.variant(variant['id']), current)
        payload['expected_bulletin_revision'] = updated['revision']
        status, _, body = self.request('POST', path, payload, headers)
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)['segments'][0]['text'], 'Nội dung đang soạn')

    def test_bulletin_rejects_article_ids_outside_sqlite_range(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử giới hạn ID',
            'url': 'https://example.com/id-range', 'summary': 'Dữ liệu giả.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        before = self.room.bulletin(bulletin['id'])
        for value in (2**63, -(2**63)-1):
            with self.subTest(article_id=value):
                status, _, body = self.request('POST', '/api/bulletins', {'article_ids': [value]}, headers)
                self.assertEqual(status, 400, body)
                status, _, body = self.request('POST', f"/api/bulletins/{bulletin['id']}/items", {
                    'revision': bulletin['revision'], 'article_id': value}, headers)
                self.assertEqual(status, 400, body)
                self.assertEqual(self.room.bulletin(bulletin['id']), before)
                self.assertEqual(len(self.room.bulletins()), 1)

    def test_legacy_draft_rejects_article_ids_outside_sqlite_range(self):
        headers = self.session()
        before = self.room.state()
        for value in (2**63, -(2**63)-1):
            with self.subTest(article_id=value):
                status, _, body = self.request('POST', '/api/drafts', {'article_id': value}, headers)
                self.assertEqual(status, 400, body)
                self.assertIn('error', json.loads(body))
        self.assertEqual(self.room.state()['drafts'], before['drafts'])

    def test_path_ids_outside_sqlite_range_are_rejected_before_dispatch(self):
        headers = self.session()
        bad_ids = (str(2**63), '9' * 5000)
        routes = [
            ('GET', '/api/bulletins/{id}'), ('GET', '/api/bulletins/{id}/packet'),
            ('GET', '/api/variants/{id}'), ('GET', '/api/variants/{id}/publications'),
            ('GET', '/api/drafts/{id}/history'), ('POST', '/api/bulletins/{id}/save'),
            ('POST', '/api/bulletins/1/items/{id}/save'), ('POST', '/api/variants/{id}/save'),
            ('POST', '/api/publications/{id}/metrics'), ('POST', '/api/drafts/{id}/copy-bulletin'),
        ]
        for bad_id in bad_ids:
            for method, route in routes:
                with self.subTest(method=method, route=route, length=len(bad_id)):
                    status, _, body = self.request(method, route.format(id=bad_id),
                        {} if method == 'POST' else None, headers)
                    self.assertEqual(status, 404, body)
                    self.assertIn('error', json.loads(body))
            status, _, body = self.request('POST', f'/api/collection/jobs/{bad_id}/run', {}, headers)
            self.assertEqual(status, 400, body)
            self.assertIn('error', json.loads(body))
        self.assertEqual(self.room.bulletins(), [])

    def test_session_reacquisition_after_server_restart_preserves_revision_guards(self):
        old = self.session()
        article = self.room.import_article({'title': 'Tin giả kiểm tra phiên',
            'url': 'https://example.com/session-recovery', 'summary': 'Dữ liệu giả.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        path = f"/api/bulletins/{bulletin['id']}/save"
        payload = {'revision': bulletin['revision'], 'title': 'Tiêu đề chưa lưu'}
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.server = make_server(self.room, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        previous_port, self.port = self.port, self.server.server_address[1]
        old['Cookie'] = old['Cookie'].replace(f'bantin_{previous_port}=', f'bantin_{self.port}=')
        old['Origin'] = f'http://127.0.0.1:{self.port}'
        self.assertEqual(self.request('POST', path, payload, old)[0], 401)
        fresh = self.session()
        old_token = dict(fresh, **{'X-CSRF-Token': old['X-CSRF-Token']})
        self.assertEqual(self.request('POST', path, payload, old_token)[0], 403)
        self.assertEqual(self.room.bulletin(bulletin['id'])['revision'], bulletin['revision'])
        status, _, body = self.request('POST', path, payload, fresh)
        self.assertEqual(status, 200, body)
        saved = json.loads(body)
        self.assertEqual(saved['title'], payload['title'])
        self.assertEqual(saved['revision'], bulletin['revision'] + 1)
        status, _, _ = self.request('POST', path, payload, fresh)
        self.assertEqual(status, 409)

    def test_absolute_form_api_target_requires_the_same_session_and_csrf(self):
        article = self.room.import_article({'title': 'Tin thử bảo vệ API',
            'url': 'https://example.com/security-test', 'summary': 'Dữ liệu thử.'})
        absolute = f'http://127.0.0.1:{self.port}'
        headers = self.session()
        payload = {'article_ids': [article['id']], 'title': 'Bản tin thử'}
        no_cookie = {key: value for key, value in headers.items() if key != 'Cookie'}
        no_csrf = {key: value for key, value in headers.items() if key != 'X-CSRF-Token'}
        get_paths = ('/api/state', '/api/bulletins', '/api/bulletin-stats',
                     '/api/legacy-publication-duplicates', '/api/bulletins/1',
                     '/api/bulletins/1/packet', '/api/bulletins/1/history', '/api/bulletins/1/variants',
                     '/api/variants/1', '/api/variants/1/export', '/api/variants/1/archive',
                     '/api/variants/1/download', '/api/variants/1/publications',
                     '/api/drafts/1/packet', '/api/drafts/1/export', '/api/drafts/1/history')
        for path in get_paths:
            for target in (path, absolute + path):
                with self.subTest(target=target):
                    self.assertEqual(self.request('GET', target)[0], 401)
        self.assertEqual(self.request('GET', absolute + '/api/state', headers=headers)[0], 200)
        self.assertEqual(self.request('POST', absolute + '/api/bulletins', payload, no_cookie)[0], 401)
        self.assertEqual(self.request('POST', absolute + '/api/bulletins', payload, no_csrf)[0], 403)
        self.assertEqual(self.request('POST', absolute + '/api/bulletins', payload,
                                      dict(headers, Origin='https://evil.example'))[0], 403)
        self.assertEqual(self.room.bulletins(), [])
        self.assertEqual(self.request('POST', absolute + '/api/bulletins', payload, headers)[0], 201)
        self.assertEqual(len(self.room.bulletins()), 1)
        self.assertEqual(self.request('GET', 'http://[bad', headers={'Host': f'127.0.0.1:{self.port}'})[0], 400)

    def test_every_multichannel_post_route_requires_session_csrf_and_origin_before_dispatch(self):
        headers = self.session()
        routes = [
            ('/api/bulletins', 'create_bulletin', 201),
            ('/api/bulletins/1/save', 'save_bulletin', 200),
            ('/api/bulletins/1/archive', 'set_bulletin_archived', 200),
            ('/api/bulletins/1/items', 'change_bulletin_items', 200),
            ('/api/bulletins/1/items/1/save', 'save_bulletin_item', 200),
            ('/api/bulletins/1/variants', 'create_variant', 200),
            ('/api/variants/1/save', 'save_variant', 200),
            ('/api/variants/1/preview', 'preview_variant', 200),
            ('/api/variants/1/split', 'split_variant', 200),
            ('/api/variants/1/approve', 'approve_variant', 200),
            ('/api/variants/1/clone', 'clone_variant', 200),
            ('/api/variants/1/publications', 'record_publication', 200),
            ('/api/publications/1/corrections', 'correct_publication', 200),
            ('/api/publications/1/metrics', 'save_publication_metrics', 200),
            ('/api/drafts/1/copy-bulletin', 'copy_legacy_draft', 200),
        ]
        no_cookie = {key: value for key, value in headers.items() if key != 'Cookie'}
        no_csrf = {key: value for key, value in headers.items() if key != 'X-CSRF-Token'}
        no_origin = {key: value for key, value in headers.items() if key != 'Origin'}
        invalid = [(no_cookie, 401), (dict(headers, Cookie='invalid=1'), 401), (no_csrf, 403),
                   (dict(headers, **{'X-CSRF-Token': 'wrong'}), 403), (no_origin, 403),
                   (dict(headers, Origin='https://evil.example'), 403), (dict(headers, Host='evil.example'), 403)]
        for path, method, expected_success in routes:
            for target in (path, f'http://127.0.0.1:{self.port}{path}'):
                with self.subTest(target=target), patch.object(self.room, method, return_value={}) as handler:
                    for rejected_headers, status in invalid:
                        self.assertEqual(self.request('POST', target, {}, rejected_headers)[0], status)
                        handler.assert_not_called()
                    self.assertEqual(self.request('POST', target, {}, headers)[0], expected_success)
                    handler.assert_called_once()

    def test_host_and_static_traversal(self):
        self.assertEqual(self.request('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        for name, content_type in (
            ('app.js', 'text/javascript'), ('draft-state.js', 'text/javascript'),
            ('source-warnings.js', 'text/javascript'), ('request-size.js', 'text/javascript'),
            ('inbox-utils.js', 'text/javascript'), ('app.css', 'text/css'),
            ('favicon.svg', 'image/svg+xml'),
        ):
            with self.subTest(asset=name):
                status, headers, body = self.request('GET', f'/static/{name}')
                self.assertEqual(status, 200)
                self.assertTrue(headers['Content-Type'].startswith(content_type))
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                self.assertIn("default-src 'self'", headers['Content-Security-Policy'])
                self.assertTrue(body)
                self.assertEqual(self.request('GET', f'/static/{name}', headers={'Host': 'evil.example'})[0], 403)
        for path in ('/static/../service.py', '/static/%2e%2e/service.py',
                     '/static/index.html', '/static/missing.js', '/static/app.js/extra'):
            with self.subTest(path=path):
                self.assertEqual(self.request('GET', path)[0], 404)

    def test_security_headers_and_import_roundtrip(self):
        headers = self.session()
        status, response_headers, body = self.request('GET', '/', headers=headers)
        self.assertIn('Content-Security-Policy', response_headers)
        self.assertIn(b'lang="vi"', body)
        self.assertIn(b'id="import-error" class="notice warning" role="alert" hidden', body)
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

    def test_non_json_numeric_constants_are_rejected_before_mutation(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử JSON',
            'url': 'https://example.com/json-constants', 'summary': 'Nguồn giả.'})
        for constant in (b'NaN', b'Infinity', b'-Infinity'):
            with self.subTest(constant=constant):
                body = b'{"article_ids":[' + str(article['id']).encode() + b'],"extra":[' + constant + b']}'
                conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
                try:
                    conn.request('POST', '/api/bulletins', body, headers)
                    response = conn.getresponse()
                    self.assertEqual(response.status, 400)
                    self.assertIn('error', json.loads(response.read()))
                finally:
                    conn.close()
                with self.room.connection() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM bulletins').fetchone()[0], 0)
        status, _, body = self.request('POST', '/api/bulletins',
            {'article_ids': [article['id']], 'title': 'NaN và Infinity là chữ'}, headers)
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)['title'], 'NaN và Infinity là chữ')

    def test_overflowing_json_float_is_rejected_before_mutation(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin thử số mũ',
            'url': 'https://example.com/json-overflow', 'summary': 'Nguồn giả.'})
        for number in (b'1e999', b'-1e999'):
            with self.subTest(number=number):
                body = b'{"article_ids":[' + str(article['id']).encode() + b'],"extra":' + number + b'}'
                conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
                try:
                    conn.request('POST', '/api/bulletins', body, headers)
                    response = conn.getresponse()
                    self.assertEqual(response.status, 400)
                    self.assertIn('error', json.loads(response.read()))
                finally:
                    conn.close()
                with self.room.connection() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM bulletins').fetchone()[0], 0)
        body = b'{"article_ids":[' + str(article['id']).encode() + b'],"extra":1.25e2}'
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.request('POST', '/api/bulletins', body, headers)
            response = conn.getresponse()
            self.assertEqual(response.status, 201)
            response.read()
        finally:
            conn.close()

    def test_deeply_nested_json_is_rejected_without_writing(self):
        headers = self.session()
        body = b'{"article_ids":' + b'[' * 20000 + b'0' + b']' * 20000 + b'}'
        self.assertLess(len(body), MAX_BODY)
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.request('POST', '/api/bulletins', body, headers)
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn('error', json.loads(response.read()))
        finally:
            conn.close()
        with self.room.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM bulletins').fetchone()[0], 0)
        self.assertEqual(self.request('GET', '/api/state', headers=headers)[0], 200)

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

    def test_legacy_duplicate_overlay_requires_session(self):
        path = '/api/legacy-publication-duplicates'
        self.assertEqual(self.request('GET', path)[0], 401)
        headers = self.session()
        drafts = []
        for index in range(2):
            article = self.room.import_article({'title': f'Tin giả {index}',
                'url': f'https://example.com/overlay-{index}', 'summary': 'Nguồn giả.'})
            drafts.append(self.room.create_draft(article['id']))
        with self.room.connection() as conn:
            for draft in drafts:
                conn.execute("UPDATE drafts SET status='published',post_url=? WHERE id=?",
                             ('https://facebook.com/page/posts/77', draft['id']))
        status, _, body = self.request('GET', path, headers=headers)
        self.assertEqual(status, 200)
        groups = json.loads(body)
        self.assertEqual([entry['id'] for entry in groups[0]['drafts']], [draft['id'] for draft in drafts])

    def test_bulletin_editorial_lifecycle_and_restart_over_http(self):
        from newsroom.bulletins import PACKET_PREFIX, PACKET_SUFFIX
        headers = self.session()

        def post(path, payload, expected=200):
            status, _, body = self.request('POST', path, payload, headers)
            self.assertEqual(status, expected, body)
            return json.loads(body)

        def get(path):
            status, _, body = self.request('GET', path, headers=headers)
            self.assertEqual(status, 200, body)
            return json.loads(body)

        articles = [post('/api/articles/import', {'title': f'Tin giả vòng đời {n}',
            'url': f'https://example.com/bulletin-lifecycle-{n}', 'summary': f'Nguồn giả ban đầu {n}.'})
            for n in range(3)]
        bulletin = post('/api/bulletins', {'article_ids': [articles[0]['id'], articles[1]['id']],
            'title': 'Bản tin vòng đời giả'}, expected=201)
        path = f"/api/bulletins/{bulletin['id']}"
        first_id, second_id = (item['id'] for item in bulletin['items'])
        first = bulletin['items'][0]
        original_source = dict(first['sources'][0])
        item_path = f'{path}/items/{first_id}/save'
        bulletin = post(item_path, {'bulletin_revision': bulletin['revision'], 'revision': first['revision'],
            'body': 'Nội dung giả do người biên tập nhập.', 'verification_note': 'Ghi chú đối chiếu riêng của người biên tập.',
            'claims': [{'text': 'Dữ kiện giả lập', 'evidence': 'Ghi chú fixture', 'checked': True}]})
        first = bulletin['items'][0]
        self.assertFalse(first['verified'])
        self.assertFalse(first['claims'][0]['checked'])
        self.assertEqual(first['sources'][0], original_source)
        bulletin = post(item_path, {'bulletin_revision': bulletin['revision'], 'revision': first['revision'],
            'verified': True, 'claims': [{**first['claims'][0], 'checked': True}]})
        first = bulletin['items'][0]
        self.assertTrue(first['verified'])
        self.assertTrue(first['claims'][0]['checked'])
        bulletin = post(item_path, {'bulletin_revision': bulletin['revision'], 'revision': first['revision'],
            'add_source': {'url': 'https://example.com/shared-lifecycle', 'title': 'Nguồn giả bổ sung',
                           'summary': 'Ghi chú nguồn giả bổ sung.'}})
        first = bulletin['items'][0]
        extra_source = first['sources'][1]
        self.assertEqual(first['sources'][0], original_source)
        self.assertFalse(first['verified'])
        self.assertFalse(first['claims'][0]['checked'])

        # Updating the inbox candidate must not rewrite the bulletin snapshot.
        refreshed = post('/api/articles/import', {'title': articles[0]['title'], 'url': articles[0]['url'],
            'summary': 'Tư liệu hộp tin giả đã thay đổi.'})
        self.assertEqual(refreshed['id'], articles[0]['id'])
        self.assertEqual(refreshed['sources'][0]['summary'], 'Tư liệu hộp tin giả đã thay đổi.')
        self.assertEqual(get(path)['items'][0]['sources'][0], original_source)
        before_revision = bulletin['revision']
        bulletin = post(path + '/save', {'revision': before_revision, 'item_ids': [second_id, first_id]})
        self.assertEqual([item['id'] for item in bulletin['items']], [second_id, first_id])
        self.assertEqual([item['position'] for item in bulletin['items']], [0, 1])
        self.assertEqual(bulletin['revision'], before_revision + 1)
        before_history = get(path + '/history')
        status, _, _ = self.request('POST', path + '/save', {'revision': before_revision,
            'item_ids': [first_id, second_id]}, headers)
        self.assertEqual(status, 409)
        self.assertEqual(get(path), bulletin)
        self.assertEqual(get(path + '/history'), before_history)

        bulletin = post(path + '/items', {'revision': bulletin['revision'], 'article_id': articles[2]['id']})
        third_id = bulletin['items'][2]['id']
        bulletin = post(path + '/items', {'revision': bulletin['revision'], 'remove_item_id': second_id})
        self.assertEqual([item['id'] for item in bulletin['items']], [first_id, third_id])
        self.assertEqual(bulletin['items'][0]['sources'][1], extra_source)
        item = bulletin['items'][0]
        bulletin = post(item_path, {'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
            'remove_source_id': extra_source['source_id']})
        self.assertEqual(bulletin['items'][0]['sources'], [original_source])
        self.assertEqual(bulletin['items'][0]['verification_note'], 'Ghi chú đối chiếu riêng của người biên tập.')
        archive = post(path + '/archive', {'revision': bulletin['revision'],
            'archive_revision': bulletin['archive_revision'], 'archived': True})
        self.assertTrue(archive['archived'])
        self.assertEqual(archive['revision'], bulletin['revision'])
        bulletin = post(path + '/archive', {'revision': archive['revision'],
            'archive_revision': archive['archive_revision'], 'archived': False})
        self.assertFalse(bulletin['archived'])
        self.assertEqual(bulletin['revision'], archive['revision'])
        packet = get(path + '/packet')
        self.assertEqual(packet['bulletin_revision'], bulletin['revision'])
        self.assertTrue(packet['text'].startswith(PACKET_PREFIX))
        self.assertTrue(packet['text'].endswith(PACKET_SUFFIX))
        self.assertEqual(json.loads(packet['text'][len(PACKET_PREFIX):-len(PACKET_SUFFIX)]), bulletin)
        history = get(path + '/history')
        self.assertEqual([event['action'] for event in history].count('bulletin_archived'), 1)
        self.assertEqual([event['action'] for event in history].count('bulletin_unarchived'), 1)
        self.assertEqual([event['action'] for event in history].count('items_changed'), 2)
        self.assertTrue(any(event['entity_type'] == 'item' and event['entity_id'] == first_id
                            and json.loads(event['snapshot'])['verification_note'] ==
                            'Ghi chú đối chiếu riêng của người biên tập.' for event in history))

        # Stop the server and reopen the same isolated store with a new session.
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.room = Newsroom(Path(self.temp.name))
        self.server = make_server(self.room, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        headers = self.session()
        self.assertEqual(get(path), bulletin)
        self.assertEqual(get(path + '/packet'), packet)
        self.assertEqual(get(path + '/history'), history)

    def test_three_channels_are_independent_and_export_exact_preview_over_http(self):
        headers = self.session()

        def post(path, payload, expected=200):
            status, _, body = self.request('POST', path, payload, headers)
            self.assertEqual(status, expected, body)
            return json.loads(body)

        def get(path, expected=200):
            status, response_headers, body = self.request('GET', path, headers=headers)
            self.assertEqual(status, expected, body)
            return response_headers, body

        articles = []
        for index in range(3):
            articles.append(post('/api/articles/import', {'title': f'Tin giả hợp đồng số {index}',
                'url': f'https://example.com/three-channel-{index}', 'summary': 'Ghi chú giả để kiểm thử.'}))
        bulletin = post('/api/bulletins', {'article_ids': [article['id'] for article in articles],
            'title': 'Bản tin ba kênh giả'}, expected=201)
        for original in bulletin['items']:
            item = next(row for row in bulletin['items'] if row['id'] == original['id'])
            item_path = f"/api/bulletins/{bulletin['id']}/items/{item['id']}/save"
            bulletin = post(item_path, {'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
                'body': 'Nội dung giả đã biên tập.', 'verification_note': 'Đối chiếu nguồn giả trên kho thử.',
                'claims': [{'text': 'Thông tin giả', 'evidence': 'Fixture', 'checked': True}]})
            item = next(row for row in bulletin['items'] if row['id'] == original['id'])
            bulletin = post(item_path, {'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
                'verified': True, 'claims': [{**item['claims'][0], 'checked': True}]})

        items = bulletin['items']
        segments = {
            'facebook': [{'text': 'Facebook giả: ba mục.', 'item_ids': [item['id'] for item in items],
                          'source_ids': [item['sources'][0]['source_id'] for item in items]}],
            'threads': [{'text': 'Threads giả: hai mục.', 'item_ids': [item['id'] for item in items[:2]],
                         'source_ids': [item['sources'][0]['source_id'] for item in items[:2]]}],
            'x': [{'text': 'Đoạn X giả thứ nhất.', 'item_ids': [items[0]['id']],
                   'source_ids': [items[0]['sources'][0]['source_id']]},
                  {'text': 'Đoạn X giả thứ hai.', 'item_ids': [items[2]['id']],
                   'source_ids': [items[2]['sources'][0]['source_id']]}],
        }
        approved = {}
        exports = {}
        for platform in ('facebook', 'threads', 'x'):
            variant = post(f"/api/bulletins/{bulletin['id']}/variants", {
                'bulletin_revision': bulletin['revision'], 'platform': platform, 'account_label': f'Kênh giả {platform}'})
            variant_path = f"/api/variants/{variant['id']}"
            variant = post(variant_path + '/save', {'revision': variant['revision'],
                'expected_bulletin_revision': bulletin['revision'], 'segments': segments[platform]})
            preview = post(variant_path + '/preview', {'segments': segments[platform]})
            self.assertTrue(preview['valid'])
            self.assertEqual(preview['bulletin_revision'], bulletin['revision'])
            self.assertFalse(preview['needs_update'])
            selected = {item_id for segment in segments[platform] for item_id in segment['item_ids']}
            self.assertEqual(preview['omitted_item_ids'], [item['id'] for item in items if item['id'] not in selected])
            for position, (rendered, segment) in enumerate(zip(preview['posts'], segments[platform])):
                self.assertEqual(rendered['item_ids'], segment['item_ids'])
                self.assertEqual(rendered['source_ids'], segment['source_ids'])
                urls = [item['sources'][0]['url'] for item in items if item['id'] in segment['item_ids']]
                self.assertEqual(rendered['urls'], urls)
                prefix = f'{position + 1}/{len(segments[platform])} ' if len(segments[platform]) > 1 else ''
                self.assertEqual(rendered['text'], prefix + segment['text'] + '\n\nNguồn: ' + ' '.join(urls))
                self.assertTrue(rendered['valid'])
            variant = post(variant_path + '/save', {'revision': variant['revision'],
                'expected_bulletin_revision': bulletin['revision'],
                'checks': {key: True for key in ('sources', 'facts', 'original', 'rights', 'claims')}})
            variant = post(variant_path + '/approve', {'revision': variant['revision'],
                'expected_bulletin_revision': bulletin['revision']})
            self.assertEqual(variant['status'], 'approved')
            _, export_body = get(variant_path + '/export')
            exported = json.loads(export_body)
            _, archive_body = get(variant_path + '/archive')
            archive = json.loads(archive_body)
            expected_posts = [post['text'] for post in preview['posts']]
            self.assertEqual(exported['posts'], expected_posts)
            self.assertEqual([post['text'] for post in archive['rendered_posts']], expected_posts)
            self.assertEqual(exported['approval_id'], archive['approval_id'])
            self.assertEqual(exported['policy_version'], preview['policy_version'])
            download_headers, downloaded = get(variant_path + '/download')
            self.assertIn('text/plain; charset=utf-8', download_headers['Content-Type'])
            self.assertEqual(downloaded, '\n\n---\n\n'.join(expected_posts).encode('utf-8'))
            approved[platform] = variant
            exports[platform] = exported
            if platform == 'facebook':
                # The first channel is usable without creating the other two.
                self.assertEqual(len(json.loads(get(f"/api/bulletins/{bulletin['id']}/variants")[1])), 1)

        self.assertTrue(exports['x']['posts'][0].startswith('1/2 '))
        self.assertTrue(exports['x']['posts'][1].startswith('2/2 '))
        facebook = approved['facebook']
        changed_segments = [{**segments['facebook'][0], 'text': 'Facebook giả đã chỉnh sửa.'}]
        changed = post(f"/api/variants/{facebook['id']}/save", {'revision': facebook['revision'],
            'expected_bulletin_revision': bulletin['revision'], 'segments': changed_segments})
        self.assertEqual(changed['status'], 'draft')
        self.assertFalse(any(changed['checks'].values()))
        self.assertEqual(self.request('GET', f"/api/variants/{facebook['id']}/export", headers=headers)[0], 400)
        for platform in ('threads', 'x'):
            path = f"/api/variants/{approved[platform]['id']}"
            self.assertEqual(json.loads(get(path)[1]), approved[platform])
            self.assertEqual(json.loads(get(path + '/export')[1]), exports[platform])
        self.assertEqual(json.loads(get('/api/bulletin-stats')[1]), {
            'bulletins': 1, 'variants': 3, 'recorded_bulletins': 0, 'recorded_posts': 0})

    def test_multichannel_response_contract_and_publication_lifecycle_over_http(self):
        headers = self.session()
        article = self.room.import_article({'title': 'Tin giả lập hợp đồng HTTP',
            'url': 'https://example.com/http-contract', 'summary': 'Tư liệu giả cho kiểm thử.'})
        bulletin = self.room.create_bulletin({'article_ids': [article['id']]})
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
            'body': 'Nội dung giả để kiểm thử hợp đồng.',
            'verification_note': 'Kiểm chứng giả lập trên dữ liệu thử.',
            'claims': [{'text': 'Dữ liệu là giả lập', 'evidence': 'Fixture', 'checked': True}]})
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
            'verified': True, 'claims': [{**item['claims'][0], 'checked': True}]})
        variant = self.room.create_variant(bulletin['id'], {'bulletin_revision': bulletin['revision'],
            'platform': 'x', 'account_label': 'Kênh giả lập'})
        segments = [{'text': 'Đoạn thử thứ nhất.', 'item_ids': [item['id']]},
                    {'text': 'Đoạn thử thứ hai.', 'item_ids': [item['id']]}]
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'], 'segments': segments})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
            'checks': {key: True for key in ('sources', 'facts', 'original', 'rights', 'claims')}})
        variant = self.room.approve_variant(variant['id'], {'revision': variant['revision']})
        path = f"/api/variants/{variant['id']}"

        def get(path):
            status, _, body = self.request('GET', path, headers=headers)
            self.assertEqual(status, 200)
            return json.loads(body)

        def post(path, data):
            status, _, body = self.request('POST', path, data, headers)
            self.assertEqual(status, 200, body)
            return json.loads(body)

        detail = get(f"/api/bulletins/{bulletin['id']}")
        self.assertEqual(detail, bulletin)
        self.assertEqual(get('/api/bulletins')[0]['item_count'], 1)
        current = get(path)
        self.assertEqual(current['status'], 'approved')
        self.assertEqual(current['publication_progress'], {'active': 0, 'total': 2})
        export = get(path + '/export')
        archive = get(path + '/archive')
        self.assertEqual(export['posts'], [post['text'] for post in archive['rendered_posts']])
        self.assertFalse(export['archive'])
        self.assertTrue(archive['archive'])
        self.assertEqual(archive['items'][0]['sources'][0]['url'], article['url'])
        preview = post(path + '/preview', {})
        self.assertEqual([row['text'] for row in preview['posts']], export['posts'])
        self.assertEqual(preview['omitted_item_ids'], [])
        self.assertFalse(preview['needs_update'])
        self.assertEqual(get('/api/bulletin-stats')['recorded_posts'], 0)

        publication_payload = {'revision': current['revision'], 'position': 0,
            'url': 'https://x.com/fixture/status/1001', 'idempotency_key': 'http_contract_1001'}
        original_respond = Handler.respond
        lost_paths = {path + '/publications'}

        def drop_response_after_commit(handler, status, data, *args, **kwargs):
            if handler.command == 'POST' and handler.path in lost_paths and status == 200:
                lost_paths.remove(handler.path)
                handler.connection.shutdown(socket.SHUT_RDWR)
                handler.close_connection = True
                return
            return original_respond(handler, status, data, *args, **kwargs)

        with patch.object(Handler, 'respond', drop_response_after_commit):
            with self.assertRaises(http.client.RemoteDisconnected):
                self.request('POST', path + '/publications', publication_payload, headers)
        self.assertEqual(get('/api/bulletin-stats')['recorded_posts'], 1)
        reported = post(path + '/publications', publication_payload)
        self.assertEqual(reported['active'], 1)
        self.assertIsNone(reported['reported_at'])
        self.assertNotIn('events', reported)
        other = self.room.create_variant(bulletin['id'], {'bulletin_revision': bulletin['revision'],
            'platform': 'x', 'account_label': 'Kênh giả khác'})
        status, _, _ = self.request('POST', f"/api/variants/{other['id']}/publications", {
            **publication_payload, 'revision': other['revision']}, headers)
        self.assertEqual(status, 409)
        self.assertEqual(get(f"/api/variants/{other['id']}/publications"), [])
        self.assertEqual(get('/api/bulletin-stats')['recorded_posts'], 1)
        current = get(path)
        self.assertEqual(current['status'], 'partially_recorded')
        status, _, body = self.request('POST', path + '/publications', {'revision': current['revision'],
            'position': 1, 'url': 'https://twitter.com/another/status/1001',
            'idempotency_key': 'http_duplicate_1001'}, headers)
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(body)['target'], {'kind': 'publication', 'bulletin_id': bulletin['id'],
            'variant_id': variant['id'], 'publication_id': reported['id'], 'position': 0})
        self.assertEqual(len(get(path + '/publications')), 1)
        self.assertEqual(current['publication_progress'], {'active': 1, 'total': 2})
        self.assertIsNotNone(current['locked_at'])
        metric = post(f"/api/publications/{reported['id']}/metrics", {
            'observed_at': '2026-11-03T10:00:00+07:00', 'views': 0})
        self.assertEqual(metric['views'], 0)
        self.assertIsNone(metric['likes'])
        self.assertEqual(metric['observed_at'], '2026-11-03T03:00:00+00:00')
        metric_path = f"/api/publications/{reported['id']}/metrics"
        metric_payload = {
            'observed_at': '2026-11-03T10:01:00+07:00', 'replies': 0, 'reposts': 3, 'quotes': None,
            'idempotency_key': 'http_metric_1001'}
        lost_paths.add(metric_path)
        with patch.object(Handler, 'respond', drop_response_after_commit):
            with self.assertRaises(http.client.RemoteDisconnected):
                self.request('POST', metric_path, metric_payload, headers)
        social_metric = post(metric_path, metric_payload)
        self.assertEqual(len(get(path + '/publications')[0]['metrics']), 2)
        self.assertEqual((social_metric['replies'], social_metric['reposts'], social_metric['quotes']), (0, 3, None))
        retry_payload = {'observed_at': '2026-11-03T10:01:00+07:00', 'replies': 0, 'reposts': 3,
                         'quotes': None, 'idempotency_key': 'http_metric_1001'}
        self.assertEqual(post(f"/api/publications/{reported['id']}/metrics", retry_payload), social_metric)
        status, _, _ = self.request('POST', f"/api/publications/{reported['id']}/metrics",
                                    {**retry_payload, 'reposts': 4}, headers)
        self.assertEqual(status, 409)
        status, _, _ = self.request('POST', f"/api/publications/{reported['id']}/metrics", {
            'observed_at': '2026-11-03T10:02:00+07:00', 'reposts': -1}, headers)
        self.assertEqual(status, 400)
        for invalid_url in (None, False, 0, [], {}):
            status, _, body = self.request('POST', f"/api/publications/{reported['id']}/corrections", {
                'revision': current['revision'], 'reason': 'Hủy ghi nhận giả lập', 'url': invalid_url}, headers)
            self.assertEqual(status, 400, body)
            self.assertEqual(get(path + '/publications')[0]['active'], 1)
            self.assertEqual(get(path)['revision'], current['revision'])
        correction = post(f"/api/publications/{reported['id']}/corrections", {
            'revision': current['revision'], 'reason': 'Hủy ghi nhận giả lập', 'url': ''})
        self.assertEqual(correction['status'], 'approved')
        self.assertEqual(post(f"/api/publications/{reported['id']}/metrics", retry_payload), social_metric)
        self.assertIsNone(correction['replacement_id'])
        records = get(path + '/publications')
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['active'], 0)
        self.assertEqual([event['action'] for event in records[0]['events']], ['reported', 'cancelled'])
        self.assertEqual(json.loads(records[0]['events'][1]['payload'])['reason'], 'Hủy ghi nhận giả lập')
        self.assertEqual(json.loads(records[0]['metrics'][0]['payload'])['views'], 0)
        self.assertEqual(len(records[0]['metrics']), 2)
        self.assertEqual(json.loads(records[0]['metrics'][1]['payload'])['reposts'], 3)
        current = get(path)
        self.assertEqual(current['publication_progress'], {'active': 0, 'total': 2})
        self.assertIsNotNone(current['locked_at'])
        self.assertEqual(get('/api/bulletin-stats')['recorded_posts'], 0)
        history = get(f"/api/bulletins/{bulletin['id']}/history")
        self.assertIsInstance(json.loads(history[0]['snapshot']), dict)
        with self.room.connection() as conn:
            conn.execute('UPDATE variant_approvals SET snapshot=? WHERE id=?', ('{', variant['approval_id']))
        for bad_path in (path, path + '/export', path + '/archive', f"/api/bulletins/{bulletin['id']}/variants"):
            status, _, body = self.request('GET', bad_path, headers=headers)
            self.assertEqual(status, 400)
            self.assertIn('Bản duyệt', json.loads(body)['error'])

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
