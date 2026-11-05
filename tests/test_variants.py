import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from newsroom.publications import normalize_post_url
from newsroom.service import Conflict, Newsroom, ValidationError
from newsroom.social_formats import count_text, render_segments, split_segments
from newsroom.variants import CHECKS, snapshot_hash


class VariantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.room = Newsroom(Path(self.temp.name))
        articles = [self.room.import_article({'title': f'Tin thử nghiệm số {n}',
            'url': f'https://example.com/story-{n}', 'summary': 'Ghi chú nguồn đã đọc và kiểm tra cẩn thận.'})
            for n in range(2)]
        bulletin = self.room.create_bulletin({'article_ids': [article['id'] for article in articles]})
        for item in list(bulletin['items']):
            current = next(row for row in bulletin['items'] if row['id'] == item['id'])
            bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
                'bulletin_revision': bulletin['revision'], 'revision': current['revision'],
                'body': 'Một mục tin được biên tập rõ ràng.',
                'verification_note': 'Đã đối chiếu nguồn gốc và ngày phát hành.',
                'claims': [{'text': 'Thông tin chính của mục', 'evidence': 'Đối chiếu nguồn đã chọn', 'checked': True}]})
            current = next(row for row in bulletin['items'] if row['id'] == item['id'])
            bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
                'bulletin_revision': bulletin['revision'], 'revision': current['revision'], 'verified': True,
                'claims': [{**current['claims'][0], 'checked': True}]})
        self.bulletin = bulletin

    def tearDown(self):
        self.temp.cleanup()

    def test_variant_save_checks_displayed_parent_revision_before_adopting(self):
        original = self.bulletin
        variant = self.room.create_variant(original['id'], {'bulletin_revision': original['revision'],
            'platform': 'x', 'account_label': 'Kênh thử'})
        updated = self.room.save_bulletin(original['id'], {'revision': original['revision'],
            'title': 'Bản tin được sửa ở thẻ khác'})
        current = self.room.variant(variant['id'])
        history = self.room.bulletin_history(original['id'])
        self.assertTrue(current['needs_update'])
        for stale in (original['revision'], None, True, str(updated['revision'])):
            with self.subTest(expected=stale), self.assertRaises(Conflict):
                self.room.save_variant(variant['id'], {'revision': current['revision'],
                    'expected_bulletin_revision': stale, 'adopt_bulletin_revision': True})
            self.assertEqual(self.room.variant(variant['id']), current)
            self.assertEqual(self.room.bulletin_history(original['id']), history)
        adopted = self.room.save_variant(variant['id'], {'revision': current['revision'],
            'expected_bulletin_revision': updated['revision'], 'adopt_bulletin_revision': True})
        self.assertEqual(adopted['bulletin_revision'], updated['revision'])
        self.assertFalse(adopted['needs_update'])
        legacy = self.room.create_variant(updated['id'], {'bulletin_revision': updated['revision'],
            'platform': 'facebook', 'account_label': 'Cũ'})
        self.assertEqual(self.room.save_variant(legacy['id'], {'revision': legacy['revision']}), legacy)

    def test_variant_actions_compare_displayed_parent_revision(self):
        original = self.bulletin
        variant = self.make_approved('x')
        updated = self.room.save_bulletin(original['id'], {'revision': original['revision'], 'title': 'Bản tin mới'})
        current = self.room.variant(variant['id'])
        current = self.room.save_variant(current['id'], {'revision': current['revision'],
            'expected_bulletin_revision': updated['revision'], 'adopt_bulletin_revision': True})
        current = self.room.save_variant(current['id'], {'revision': current['revision'],
            'checks': {key: True for key in CHECKS}})
        current = self.room.approve_variant(current['id'], {'revision': current['revision']})
        preview = self.room.preview_variant(current['id'], {})
        self.assertFalse(preview['needs_update'])
        self.assertEqual(preview['bulletin_revision'], updated['revision'])
        before_history = self.room.bulletin_history(original['id'])
        before_variants = self.room.variants(original['id'])
        request = {'revision': current['revision'], 'expected_bulletin_revision': original['revision']}
        for action in (self.room.split_variant, self.room.clone_variant, self.room.approve_variant):
            with self.subTest(action=action.__name__), self.assertRaises(Conflict):
                action(current['id'], request)
            self.assertEqual(self.room.variants(original['id']), before_variants)
            self.assertEqual(self.room.bulletin_history(original['id']), before_history)
        request['expected_bulletin_revision'] = updated['revision']
        self.assertTrue(self.room.split_variant(current['id'], request)['preview']['valid'])
        self.assertEqual(self.room.clone_variant(current['id'], request)['status'], 'draft')
        self.assertEqual(self.room.approve_variant(current['id'], request)['status'], 'approved')

    def test_multichannel_workflow_does_not_make_network_connections(self):
        # Exercise real service methods on a temporary SQLite store while
        # refusing outgoing connections, including the migration of a new store.
        with patch('socket.create_connection', side_effect=AssertionError('Unexpected network')), \
             patch('socket.socket.connect', side_effect=AssertionError('Unexpected network')), \
             tempfile.TemporaryDirectory() as directory:
            fresh = Newsroom(Path(directory))
            article = fresh.import_article({'title': 'Tin giả lập',
                'url': 'https://example.com/offline', 'summary': 'Nguồn giả lập.'})
            bulletin = fresh.create_bulletin({'article_ids': [article['id']]})
            item = bulletin['items'][0]
            bulletin = fresh.save_bulletin_item(bulletin['id'], item['id'], {
                'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
                'body': 'Nội dung giả lập.', 'verification_note': 'Đã đối chiếu nguồn giả lập trong kho thử.',
                'claims': [{'text': 'Khẳng định giả', 'evidence': 'Nguồn giả', 'checked': True}]})
            item = bulletin['items'][0]
            bulletin = fresh.save_bulletin_item(bulletin['id'], item['id'], {
                'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
                'verified': True, 'claims': [{**item['claims'][0], 'checked': True}]})
            self.assertIn('https://example.com/offline', fresh.bulletin_packet(bulletin['id']))
            variant = fresh.create_variant(bulletin['id'], {'bulletin_revision': bulletin['revision'],
                'platform': 'x', 'account_label': 'Kênh giả'})
            variant = fresh.save_variant(variant['id'], {'revision': variant['revision'],
                'segments': [{'text': 'Bản tin giả.', 'item_ids': [item['id']]}]})
            preview = fresh.preview_variant(variant['id'])
            variant = fresh.save_variant(variant['id'], {'revision': variant['revision'],
                'checks': {key: True for key in CHECKS}})
            variant = fresh.approve_variant(variant['id'], {'revision': variant['revision']})
            exported = fresh.export_variant(variant['id'])
            self.assertEqual(exported['posts'], [post['text'] for post in preview['posts']])
            fresh.record_publication(variant['id'], {'revision': variant['revision'], 'position': 0,
                'url': 'https://x.com/test/status/123', 'idempotency_key': 'offline_test_123'})
            self.assertEqual(fresh.variant(variant['id'])['publication_progress']['active'], 1)

    def make_approved(self, platform='x', two=False):
        variant = self.room.create_variant(self.bulletin['id'], {'platform': platform, 'account_label': 'Kênh thử',
                                               'bulletin_revision': self.bulletin['revision']})
        ids = [item['id'] for item in self.bulletin['items']]
        segments = ([{'text': 'Một tin hữu ích cho công việc.', 'item_ids': [ids[0]]},
                     {'text': 'Một tin khác cần kiểm tra.', 'item_ids': [ids[1]]}]
                    if two else [{'text': 'Bản tin hữu ích cho công việc.', 'item_ids': ids}])
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'], 'segments': segments})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
                                                          'checks': {key: True for key in CHECKS}})
        return self.room.approve_variant(variant['id'], {'revision': variant['revision']})

    def make_approved_legacy(self):
        article_id = self.bulletin['items'][0]['article_id']
        draft = self.room.create_draft(article_id)
        draft = self.room.save_draft(draft['id'], {
            'revision': draft['revision'], 'title': 'Bài kiểm thử legacy',
            'body': 'Nội dung kiểm thử có đủ thông tin để biên tập. ' * 5,
            'angle': 'Giải thích lợi ích và giới hạn.', 'page_name': 'Trang thử',
        })
        draft = self.room.save_draft(draft['id'], {
            'revision': draft['revision'], 'checks': {key: True for key in self.room.CHECKS}})
        return self.room.approve(draft['id'], draft['revision'])

    def test_editing_facebook_preserves_other_approved_variants_after_reopen(self):
        facebook = self.make_approved('facebook')
        threads = self.make_approved('threads')
        x = self.make_approved('x')
        before = {variant['id']: (self.room.variant(variant['id']), self.room.export_variant(variant['id']))
                  for variant in (threads, x)}
        segment = {**facebook['segments'][0], 'text': 'Nội dung Facebook đã chỉnh sửa.'}
        saved = self.room.save_variant(facebook['id'], {'revision': facebook['revision'], 'segments': [segment]})
        self.assertEqual(saved['status'], 'draft')
        self.assertGreater(saved['revision'], facebook['revision'])
        reopened = Newsroom(self.room.data_dir)
        self.assertEqual(reopened.variant(facebook['id'])['segments'][0]['text'], segment['text'])
        for variant_id, (old_variant, old_export) in before.items():
            with self.subTest(variant_id=variant_id):
                self.assertEqual(reopened.variant(variant_id), old_variant)
                self.assertEqual(reopened.export_variant(variant_id), old_export)

    def test_clone_edited_variant_and_reject_stale_save_without_overwriting(self):
        original = self.make_approved('x')
        edited = self.room.save_variant(original['id'], {'revision': original['revision'],
            'segments': [{**original['segments'][0], 'text': 'Nội dung đã biên tập.'}]})
        clone = self.room.clone_variant(edited['id'], {'revision': edited['revision'],
            'expected_bulletin_revision': self.bulletin['revision']})
        self.assertNotEqual(clone['id'], edited['id'])
        self.assertEqual(clone['status'], 'draft')
        self.assertEqual(clone['segments'][0]['text'], edited['segments'][0]['text'])
        self.assertEqual(clone['segments'][0]['item_ids'], edited['segments'][0]['item_ids'])
        self.assertEqual(set(clone['segments'][0]['source_ids']),
                         {source['source_id'] for item in self.bulletin['items'] for source in item['sources']})
        winner = self.room.save_variant(clone['id'], {'revision': clone['revision'],
            'segments': [{**clone['segments'][0], 'text': 'Bản lưu thứ nhất.'}]})
        with self.assertRaises(Conflict):
            self.room.save_variant(clone['id'], {'revision': clone['revision'],
                'segments': [{**clone['segments'][0], 'text': 'Bản lưu revision cũ.'}]})
        reopened = Newsroom(self.room.data_dir)
        self.assertEqual(reopened.variant(edited['id']), edited)
        self.assertEqual(reopened.variant(clone['id']), winner)

    def test_archiving_bulletin_preserves_approved_and_recorded_versions(self):
        from newsroom.__main__ import restore

        recorded = self.make_approved(two=True)
        publication = self.room.record_publication(recorded['id'], {
            'revision': recorded['revision'], 'position': 0,
            'url': 'https://x.com/fixture/status/76001', 'idempotency_key': 'archive_fixture_76001'})
        self.room.save_publication_metrics(publication['id'], {
            'observed_at': '2026-11-04T10:00:00+07:00', 'views': 0})
        unpublished = self.make_approved(platform='threads')
        before = self.room.bulletin(self.bulletin['id'])
        self.assertFalse(before['archived'])
        self.assertEqual(before['archive_revision'], 0)
        before_variants = {key: self.room.variant(key) for key in (recorded['id'], unpublished['id'])}
        before_exports = {key: self.room.export_variant(key) for key in before_variants}
        before_publications = self.room.publications(recorded['id'])
        before_stats = self.room.bulletin_stats()

        archived = self.room.set_bulletin_archived(before['id'], {
            'revision': before['revision'], 'archive_revision': before['archive_revision'], 'archived': True})
        self.assertTrue(archived['archived'])
        self.assertGreater(archived['archive_revision'], 0)
        self.assertEqual(archived['revision'], before['revision'])
        self.assertEqual(archived['items'], before['items'])
        self.assertTrue(next(row for row in self.room.bulletins() if row['id'] == before['id'])['archived'])
        for key in before_variants:
            self.assertEqual(self.room.variant(key), before_variants[key])
            self.assertEqual(self.room.export_variant(key), before_exports[key])
        self.assertEqual(self.room.publications(recorded['id']), before_publications)
        self.assertEqual(self.room.bulletin_stats(), before_stats)
        with self.assertRaises(Conflict):
            self.room.set_bulletin_archived(before['id'], {
                'revision': before['revision'], 'archive_revision': 0, 'archived': False})
        self.assertTrue(self.room.bulletin(before['id'])['archived'])

        target = Path(self.temp.name) / 'archived-restore'
        restore(self.room.backup(), target)
        reopened = Newsroom(target)
        self.assertTrue(reopened.bulletin(before['id'])['archived'])
        self.assertEqual(reopened.publications(recorded['id']), before_publications)
        self.assertEqual(reopened.export_variant(unpublished['id']), before_exports[unpublished['id']])

        restored = self.room.set_bulletin_archived(before['id'], {
            'revision': archived['revision'], 'archive_revision': archived['archive_revision'], 'archived': False})
        self.assertFalse(restored['archived'])
        self.assertGreater(restored['archive_revision'], archived['archive_revision'])
        self.assertEqual(restored['revision'], before['revision'])
        self.assertEqual(self.room.publications(recorded['id']), before_publications)
        self.assertEqual(self.room.export_variant(unpublished['id']), before_exports[unpublished['id']])
        actions = [entry['action'] for entry in self.room.bulletin_history(before['id'])]
        self.assertEqual(actions.count('bulletin_archived'), 1)
        self.assertEqual(actions.count('bulletin_unarchived'), 1)

    def test_legacy_duplicate_overlay_preserves_original_records(self):
        drafts = [self.make_approved_legacy() for _ in range(3)]
        urls = ['https://facebook.com/page/posts/77',
                'https://m.facebook.com/page/posts/77?ref=share',
                'https://facebook.com/other/posts/88']
        with self.room.connection() as conn:
            for draft, url in zip(drafts, urls):
                conn.execute("UPDATE drafts SET status='published',post_url=? WHERE id=?", (url, draft['id']))
            before = [tuple(row) for row in conn.execute('SELECT * FROM drafts ORDER BY id')]
        groups = self.room.legacy_publication_duplicates()
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['match'], 'recognized')
        self.assertEqual([entry['id'] for entry in groups[0]['drafts']], [drafts[0]['id'], drafts[1]['id']])
        self.assertEqual([entry['url'] for entry in groups[0]['drafts']], urls[:2])
        with self.room.connection() as conn:
            self.assertEqual(before, [tuple(row) for row in conn.execute('SELECT * FROM drafts ORDER BY id')])
            conn.execute('UPDATE drafts SET post_url=? WHERE id=?', ('https://facebook.com/reel/123?utm_source=share', drafts[0]['id']))
            conn.execute('UPDATE drafts SET post_url=? WHERE id=?', ('https://m.facebook.com/reel/123', drafts[1]['id']))
        groups = self.room.legacy_publication_duplicates()
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['match'], 'exact')
        self.assertEqual([entry['id'] for entry in groups[0]['drafts']], [drafts[0]['id'], drafts[1]['id']])

    def test_legacy_and_variant_cannot_claim_same_facebook_post_in_either_order(self):
        legacy = self.make_approved_legacy()
        variant = self.make_approved('facebook')
        recorded = self.room.record_publication(variant['id'], {'revision': variant['revision'], 'position': 0,
            'url': 'https://www.facebook.com/page/posts/100', 'idempotency_key': 'cross_claim_100'})
        with self.assertRaises(Conflict) as caught:
            self.room.mark_published(legacy['id'], legacy['revision'], 'https://m.facebook.com/page/posts/100?ref=share')
        self.assertEqual(caught.exception.target, {'kind': 'publication', 'bulletin_id': self.bulletin['id'],
            'variant_id': variant['id'], 'publication_id': recorded['id'], 'position': 0})
        self.assertEqual(self.room.draft(legacy['id'])['status'], 'approved')

        legacy = self.make_approved_legacy()
        self.room.mark_published(legacy['id'], legacy['revision'], 'https://facebook.com/page/posts/200')
        another = self.make_approved('facebook')
        with self.assertRaises(Conflict) as caught:
            self.room.record_publication(another['id'], {'revision': another['revision'], 'position': 0,
                'url': 'https://m.facebook.com/page/posts/200?ref=share', 'idempotency_key': 'cross_claim_200'})
        self.assertEqual(caught.exception.target, {'kind': 'legacy_draft', 'draft_id': legacy['id']})
        self.assertEqual(self.room.variant(another['id'])['status'], 'approved')

    def test_two_legacy_drafts_cannot_claim_same_facebook_post(self):
        first = self.make_approved_legacy()
        second = self.make_approved_legacy()
        self.room.mark_published(first['id'], first['revision'], 'https://facebook.com/page/posts/300')
        with self.assertRaises(Conflict):
            self.room.mark_published(second['id'], second['revision'], 'https://m.facebook.com/page/posts/300?ref=share')
        self.assertEqual(self.room.draft(second['id'])['status'], 'approved')

    def test_legacy_and_variant_competing_for_same_url_have_one_winner(self):
        legacy = self.make_approved_legacy()
        variant = self.make_approved('facebook')
        barrier = threading.Barrier(2)

        def claim(kind):
            barrier.wait(timeout=5)
            try:
                if kind == 'legacy':
                    self.room.mark_published(legacy['id'], legacy['revision'],
                                             'https://m.facebook.com/page/posts/400?ref=share')
                else:
                    self.room.record_publication(variant['id'], {'revision': variant['revision'], 'position': 0,
                        'url': 'https://www.facebook.com/page/posts/400', 'idempotency_key': 'cross_race_400'})
                return 'recorded'
            except Conflict:
                return 'conflict'

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(claim, ('legacy', 'variant')))
        self.assertCountEqual(outcomes, ['recorded', 'conflict'])

    def test_format_counts_and_source_links(self):
        self.assertEqual(count_text('x', 'english text 日本語 😷 https://example.com')[0], 46)
        self.assertEqual(count_text('x', '🙋🏽👨‍🎤')[0], 4)
        self.assertEqual(count_text('threads', 'a😷')[0], 2)
        item = self.bulletin['items'][0]
        result = render_segments('x', [{'text': 'x' * 255, 'item_ids': [item['id']]}], self.bulletin)
        self.assertFalse(result['valid'])  # source URL and its label count too
        self.assertIn(item['sources'][0]['url'], result['posts'][0]['text'])

    def test_x_url_weight_and_boundary(self):
        for url in ('https://t.co/a', 'https://example.com/' + 'long-path-' * 15):
            with self.subTest(url=url):
                self.assertEqual(count_text('x', url), (23, True))
                self.assertEqual(count_text('x', 'a' * 256 + ' ' + url), (280, True))
                self.assertEqual(count_text('x', 'a' * 257 + ' ' + url), (281, False))

    def test_threads_estimate_matches_observed_composer_unicode_samples(self):
        # Observed on the Threads web composer, 2026-11-05; not a complete policy.
        samples = {'café': 4, 'cafe\u0301': 5, '😷': 1, '👍🏽': 2,
                   '🇻🇳': 2, '❤️': 2, '👨‍👩‍👧‍👦': 7, '𠀀🫨': 2,
                   'https://example.com/very-long-article-url-123456789': 51}
        for sample, length in samples.items():
            with self.subTest(sample=sample):
                self.assertEqual(count_text('threads', sample), (length, True))
                self.assertEqual(count_text('threads', 'a' * (500 - length) + sample), (500, True))
                self.assertEqual(count_text('threads', 'a' * (501 - length) + sample), (501, False))

    def test_approval_requires_each_claim_checked_with_evidence(self):
        item = self.bulletin['items'][0]
        modified = self.room.save_bulletin_item(self.bulletin['id'], item['id'], {
            'bulletin_revision': self.bulletin['revision'], 'revision': item['revision'],
            'claims': [{'text': 'Một dữ kiện cần xác minh', 'evidence': '', 'checked': False}]})
        item = modified['items'][0]
        self.room.save_bulletin_item(modified['id'], item['id'], {
            'bulletin_revision': modified['revision'], 'revision': item['revision'], 'verified': True})
        self.bulletin = self.room.bulletin(modified['id'])
        with self.assertRaises(ValidationError):
            self.make_approved('threads')

    def test_approval_rejects_unresolved_markers_in_editorial_item_fields(self):
        for field in ('title', 'body', 'angle', 'verification_note'):
            with self.subTest(field=field):
                item = self.bulletin['items'][0]
                edited = self.room.save_bulletin_item(self.bulletin['id'], item['id'], {
                    'bulletin_revision': self.bulletin['revision'], 'revision': item['revision'],
                    field: 'Thông tin [CẦN KIỂM TRA] trước khi đăng.'})
                item = edited['items'][0]
                self.bulletin = self.room.save_bulletin_item(edited['id'], item['id'], {
                    'bulletin_revision': edited['revision'], 'revision': item['revision'], 'verified': True,
                    'claims': [{**item['claims'][0], 'checked': True}]})
                with self.assertRaises(ValidationError) as caught:
                    self.make_approved('facebook')
                label = {'title': 'tiêu đề', 'body': 'nội dung', 'angle': 'góc nhìn',
                         'verification_note': 'ghi chú kiểm chứng'}[field]
                self.assertIn('mục 1', str(caught.exception))
                self.assertIn(label, str(caught.exception))
                item = self.bulletin['items'][0]
                edited = self.room.save_bulletin_item(self.bulletin['id'], item['id'], {
                    'bulletin_revision': self.bulletin['revision'], 'revision': item['revision'],
                    field: 'Thông tin đã đối chiếu nguồn phù hợp.'})
                item = edited['items'][0]
                self.bulletin = self.room.save_bulletin_item(edited['id'], item['id'], {
                    'bulletin_revision': edited['revision'], 'revision': item['revision'], 'verified': True,
                    'claims': [{**item['claims'][0], 'checked': True}]})
        self.assertEqual(self.make_approved('facebook')['status'], 'approved')

    def test_older_approval_requires_review_after_editorial_policy_change(self):
        with patch('newsroom.variants.POLICY_VERSION', '2026-11-03-v3'):
            variant = self.make_approved('facebook')
        self.assertTrue(self.room.variant(variant['id'])['policy_stale'])
        with self.assertRaises(ValidationError):
            self.room.export_variant(variant['id'])
        self.assertTrue(self.room.export_variant(variant['id'], archive=True)['archive'])

    def test_v5_approvals_require_review_with_v6_and_keep_archive(self):
        for platform in ('facebook', 'threads', 'x'):
            with self.subTest(platform=platform):
                with patch('newsroom.variants.POLICY_VERSION', '2026-11-04-v5'), \
                     patch('newsroom.social_formats.POLICY_VERSION', '2026-11-04-v5'):
                    variant = self.make_approved(platform)
                    old = self.room.export_variant(variant['id'], archive=True)
                self.assertTrue(self.room.variant(variant['id'])['policy_stale'])
                with self.assertRaises(ValidationError):
                    self.room.export_variant(variant['id'])
                archived = self.room.export_variant(variant['id'], archive=True)
                self.assertEqual(archived, old)

    def test_approval_rejects_missing_claim_or_evidence_and_unresolved_markers(self):
        cases = [[],
                 [{'text': 'Dữ kiện', 'evidence': '', 'checked': True}],
                 [{'text': '[CẦN KIỂM TRA] Dữ kiện', 'evidence': 'Nguồn', 'checked': True}],
                 [{'text': 'Dữ kiện', 'evidence': '[CẦN KIỂM TRA]', 'checked': True}]]
        for claims in cases:
            with self.subTest(claims=claims):
                item = self.bulletin['items'][0]
                self.bulletin = self.room.save_bulletin_item(self.bulletin['id'], item['id'], {
                    'bulletin_revision': self.bulletin['revision'], 'revision': item['revision'], 'claims': claims})
                item = self.bulletin['items'][0]
                self.bulletin = self.room.save_bulletin_item(self.bulletin['id'], item['id'], {
                    'bulletin_revision': self.bulletin['revision'], 'revision': item['revision'],
                    'claims': claims, 'verified': True})
                with self.assertRaises(ValidationError):
                    self.make_approved('threads')

    def test_approval_counts_crlf_in_final_x_post_including_source(self):
        item = self.bulletin['items'][0]
        source = item['sources'][0]['source_id']
        template = {'text': 'A', 'item_ids': [item['id']], 'source_ids': [source]}
        suffix_weight = render_segments('x', [template], self.bulletin)['posts'][0]['length'] - 1
        body = 'A' * (278 - suffix_weight) + '\r\nB'
        segment = {**template, 'text': body}
        rendered = render_segments('x', [segment], self.bulletin)
        self.assertEqual(rendered['posts'][0]['length'], 281)
        self.assertFalse(rendered['valid'])
        variant = self.room.create_variant(self.bulletin['id'], {'platform': 'x', 'account_label': 'Kênh thử',
                                               'bulletin_revision': self.bulletin['revision']})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'], 'segments': [segment]})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
                                                          'checks': {key: True for key in CHECKS}})
        with self.assertRaises(ValidationError):
            self.room.approve_variant(variant['id'], {'revision': variant['revision']})
        self.assertEqual(self.room.variant(variant['id'])['status'], 'draft')

    def test_split_rechecks_numbering_and_keeps_sources_and_text(self):
        item = self.bulletin['items'][0]
        # Each sentence fits alone, but two do not. The last index crosses 9→10.
        sentences = [f'Câu {i}: ' + ('n' * 145) + f' 😷 https://example.com/a{i}.' for i in range(1, 11)]
        original = ' '.join(sentences)
        segments = [{'text': original, 'item_ids': [item['id']],
                     'source_ids': [item['sources'][0]['source_id']]}]
        split = split_segments('x', segments, self.bulletin)
        self.assertEqual(len(split), 10)
        self.assertEqual(' '.join(segment['text'].strip() for segment in split), original)
        self.assertEqual(''.join(segment['text'] for segment in split), original)
        self.assertTrue(all(segment['source_ids'] == segments[0]['source_ids'] for segment in split))
        rendered = render_segments('x', split, self.bulletin)
        self.assertTrue(rendered['valid'])
        self.assertTrue(rendered['posts'][-1]['text'].startswith('10/10 '))
        self.assertTrue(all(item['sources'][0]['url'] in post['text'] for post in rendered['posts']))

    def test_split_rejects_unsplittable_text_without_cutting(self):
        item = self.bulletin['items'][0]
        segments = [{'text': '😀' * 400, 'item_ids': [item['id']]}]
        with self.assertRaisesRegex(ValidationError, 'chia an toàn'):
            split_segments('x', segments, self.bulletin)
        self.assertEqual(segments[0]['text'], '😀' * 400)

    def test_split_twenty_post_boundary_and_rejection_preserves_saved_draft(self):
        item = self.bulletin['items'][0]
        source_id = item['sources'][0]['source_id']
        for platform, width in (('x', 160), ('threads', 300)):
            with self.subTest(platform=platform):
                # One sentence fits with its source and numbering; two cannot.
                sentences = [f'{number}: ' + 'a' * width + '.' for number in range(1, 22)]
                original = ' '.join(sentences[:20])
                segment = {'text': original, 'item_ids': [item['id']], 'source_ids': [source_id]}
                result = split_segments(platform, [segment], self.bulletin)
                self.assertEqual(len(result), 20)
                self.assertEqual(''.join(part['text'] for part in result), original)
                preview = render_segments(platform, result, self.bulletin)
                self.assertTrue(preview['valid'])
                for index, post in enumerate(preview['posts'], 1):
                    self.assertTrue(post['text'].startswith(f'{index}/20 '))
                    self.assertIn(item['sources'][0]['url'], post['text'])
                too_long = ' '.join(sentences)
                variant = self.room.create_variant(self.bulletin['id'], {
                    'platform': platform, 'account_label': 'Kho thử',
                    'bulletin_revision': self.bulletin['revision']})
                variant = self.room.save_variant(variant['id'], {
                    'revision': variant['revision'], 'segments': [{**segment, 'text': too_long}]})
                with self.assertRaisesRegex(ValidationError, 'quá 20 đoạn'):
                    self.room.split_variant(variant['id'], {'revision': variant['revision']})
                reopened = Newsroom(self.room.data_dir).variant(variant['id'])
                self.assertEqual(reopened['revision'], variant['revision'])
                self.assertEqual(reopened['segments'], variant['segments'])
                self.assertEqual(reopened['segments'][0]['text'], too_long)

    def test_approval_rejects_used_excerpt_with_mismatched_hash(self):
        import hashlib
        item = self.bulletin['items'][0]
        with self.room.connection() as conn:
            row = conn.execute('SELECT payload FROM bulletin_items WHERE id=?', (item['id'],)).fetchone()
            payload = json.loads(row['payload'])
            payload['sources'][0].update({'collection_method': 'api', 'excerpt_hash': '0' * 64,
                                          'content_hash': 'a' * 64, 'scope': 'excerpt'})
            conn.execute('UPDATE bulletin_items SET payload=? WHERE id=?', (json.dumps(payload), item['id']))
        variant = self.room.create_variant(self.bulletin['id'], {'platform': 'x', 'account_label': 'Kênh thử',
                                               'bulletin_revision': self.bulletin['revision']})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'], 'segments': [
            {'text': 'Nội dung thử.', 'item_ids': [item['id']]}]})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
                                                          'checks': {key: True for key in CHECKS}})
        with self.assertRaisesRegex(ValidationError, 'hash.*trích đoạn.*mục 1.*nguồn 1'):
            self.room.approve_variant(variant['id'], {'revision': variant['revision']})
        self.assertEqual(self.room.variant(variant['id'])['status'], 'draft')
        payload['sources'][0]['excerpt_hash'] = hashlib.sha256(payload['sources'][0]['summary'].encode('utf-8')).hexdigest()
        with self.room.connection() as conn:
            conn.execute('UPDATE bulletin_items SET payload=? WHERE id=?', (json.dumps(payload), item['id']))
            unused_id = self.bulletin['items'][1]['id']
            unused = json.loads(conn.execute('SELECT payload FROM bulletin_items WHERE id=?', (unused_id,)).fetchone()['payload'])
            unused['sources'][0]['excerpt_hash'] = '0' * 64
            conn.execute('UPDATE bulletin_items SET payload=? WHERE id=?', (json.dumps(unused), unused_id))
        approved = self.room.approve_variant(variant['id'], {'revision': variant['revision']})
        self.assertEqual(approved['status'], 'approved')

    def test_split_preserves_boundary_whitespace_in_editable_segments(self):
        item = self.bulletin['items'][0]
        segment = {'item_ids': [item['id']], 'source_ids': [item['sources'][0]['source_id']]}
        for platform in ('x', 'threads'):
            for boundary in ('\n\n  \t', '\r\n\r\n  \t'):
                with self.subTest(platform=platform, boundary=repr(boundary)):
                    original = '  ' + ('A' * 170) + '.' + boundary + ('B' * 170) + '.  '
                    # Repeat the text for Threads so the result must span posts.
                    text = original if platform == 'x' else original + boundary + original
                    result = split_segments(platform, [{**segment, 'text': text}], self.bulletin)
                    self.assertGreater(len(result), 1)
                    self.assertEqual(''.join(part['text'] for part in result), text)
                    self.assertTrue(all(part['source_ids'] == segment['source_ids'] for part in result))
                    self.assertTrue(render_segments(platform, result, self.bulletin)['valid'])

    def test_split_suggestion_preserves_whitespace_when_saved_and_reopened(self):
        item = self.bulletin['items'][0]
        original = '  ' + ('A' * 170) + '.\n\n  ' + ('B' * 170) + '.  '
        variant = self.room.create_variant(self.bulletin['id'], {'platform': 'x', 'account_label': 'Fixture',
                                          'bulletin_revision': self.bulletin['revision']})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'], 'segments': [
            {'text': original, 'item_ids': [item['id']], 'source_ids': [item['sources'][0]['source_id']]}]})
        suggestion = self.room.split_variant(variant['id'], {'revision': variant['revision']})
        self.assertEqual(self.room.variant(variant['id'])['segments'][0]['text'], original)
        self.assertEqual(''.join(part['text'] for part in suggestion['segments']), original)
        saved = self.room.save_variant(variant['id'], {'revision': variant['revision'], 'segments': suggestion['segments']})
        reopened = Newsroom(self.room.data_dir).variant(saved['id'])
        self.assertEqual(''.join(part['text'] for part in reopened['segments']), original)
        preview = self.room.preview_variant(saved['id'])
        self.assertEqual([post['text'] for post in preview['posts']],
                         [post['text'] for post in suggestion['preview']['posts']])

    def test_split_preserves_internal_blank_lines(self):
        item = self.bulletin['items'][0]
        original = 'Đoạn đầu.\n\n\n\nĐoạn tiếp theo.'
        segments = [{'text': original, 'item_ids': [item['id']]}]
        result = split_segments('x', segments, self.bulletin)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], original)
        first = 'A' * 100 + '.\n\n\n\n' + 'B' * 40 + '.'
        second = 'C' * 100 + '.\n\n\n\n' + 'D' * 40 + '.'
        result = split_segments('x', [{'text': first + ' ' + second, 'item_ids': [item['id']]}], self.bulletin)
        self.assertEqual([entry['text'].strip() for entry in result], [first, second])
        self.assertEqual(''.join(entry['text'] for entry in result), first + ' ' + second)

    def test_approved_export_matches_preview_and_changes_invalidate(self):
        variant = self.make_approved('threads')
        preview = self.room.preview_variant(variant['id'])
        exported = self.room.export_variant(variant['id'])
        self.assertEqual(exported['approval_id'], variant['approval_id'])
        self.assertEqual(exported['posts'], [post['text'] for post in preview['posts']])
        self.assertFalse(preview['needs_update'])
        self.room.save_bulletin(self.bulletin['id'], {'revision': self.bulletin['revision'], 'title': 'Đổi bản tin'})
        self.assertTrue(self.room.variant(variant['id'])['needs_update'])
        self.assertTrue(self.room.preview_variant(variant['id'])['needs_update'])
        with self.assertRaises(ValidationError):
            self.room.export_variant(variant['id'])

    def test_corrupt_approval_fails_closed_before_read_export_or_record(self):
        variant = self.make_approved('x')
        with self.room.connection() as conn:
            original = dict(conn.execute('SELECT * FROM variant_approvals WHERE id=?', (variant['approval_id'],)).fetchone())
        malformed_shape = {'policy_version': 'bad', 'rendered': {}}
        corrupt = [('{', original['approved_hash']), ('{}', original['approved_hash']),
                   (json.dumps(malformed_shape), snapshot_hash(malformed_shape))]
        for payload, digest in corrupt:
            with self.subTest(payload=payload), self.room.connection() as conn:
                conn.execute('UPDATE variant_approvals SET snapshot=?,approved_hash=? WHERE id=?',
                             (payload, digest, variant['approval_id']))
            for operation in (lambda: self.room.variant(variant['id']),
                              lambda: self.room.variants(self.bulletin['id']),
                              lambda: self.room.export_variant(variant['id']),
                              lambda: self.room.export_variant(variant['id'], archive=True),
                              lambda: self.room.record_publication(variant['id'], {'revision': variant['revision'],
                                  'position': 0, 'url': 'https://x.com/test/status/999', 'idempotency_key': 'corrupt_999'})):
                with self.assertRaisesRegex(ValidationError, 'Bản duyệt'):
                    operation()
            with self.room.connection() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM publications').fetchone()[0], 0)
                row = conn.execute('SELECT snapshot,approved_hash FROM variant_approvals WHERE id=?',
                                   (variant['approval_id'],)).fetchone()
                self.assertEqual(tuple(row), (payload, digest))
        with self.room.connection() as conn:
            conn.execute('UPDATE variant_approvals SET snapshot=?,approved_hash=? WHERE id=?',
                         (original['snapshot'], original['approved_hash'], variant['approval_id']))
        self.assertTrue(self.room.export_variant(variant['id'])['posts'])

    def test_parent_edit_resets_checks_of_unlocked_variants_only(self):
        unlocked = self.make_approved('threads')
        locked = self.make_approved('x')
        self.room.record_publication(locked['id'], {'revision': locked['revision'], 'position': 0,
            'url': 'https://x.com/test/status/991', 'idempotency_key': 'parent_edit_991'})
        before_locked = self.room.variant(locked['id'])
        archived_before = self.room.export_variant(locked['id'], archive=True)
        self.room.save_bulletin(self.bulletin['id'], {
            'revision': self.bulletin['revision'], 'title': 'Bản tin đã chỉnh sửa'})
        updated = self.room.variant(unlocked['id'])
        self.assertEqual(updated['status'], 'draft')
        self.assertTrue(updated['needs_update'])
        self.assertFalse(any(updated['checks'].values()))
        self.assertEqual(self.room.variant(locked['id']), before_locked)
        self.assertEqual(self.room.export_variant(locked['id'], archive=True), archived_before)
        with self.assertRaises(Conflict):
            self.room.approve_variant(unlocked['id'], {'revision': updated['revision']})

    def test_export_reads_variant_and_approval_in_one_snapshot(self):
        variant = self.make_approved('threads')
        with self.room.connection() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
        original = self.room._approved_variant
        observed = []

        def concurrent_edit(conn, selected, archive=False):
            observed.append(conn.in_transaction)
            self.room.save_bulletin(self.bulletin['id'], {
                'revision': self.bulletin['revision'], 'title': 'Bản tin đã thay đổi'})
            return original(conn, selected, archive=archive)

        with patch.object(self.room, '_approved_variant', side_effect=concurrent_edit):
            exported = self.room.export_variant(variant['id'])
        self.assertEqual(observed, [True])
        self.assertIn('Bản tin hữu ích', exported['posts'][0])
        self.assertEqual(self.room.variant(variant['id'])['status'], 'draft')
        with self.assertRaises(ValidationError):
            self.room.export_variant(variant['id'])

    def test_variant_read_is_consistent_during_publication(self):
        import newsroom.variants as variant_module
        variant = self.make_approved('x')
        original = variant_module.approval_snapshot
        inserted = []

        def publish_after_approval_read(row):
            snapshot = original(row)
            if not inserted:
                inserted.append(True)
                self.room.record_publication(variant['id'], {
                    'revision': variant['revision'], 'position': 0,
                    'url': 'https://x.com/test/status/123456', 'idempotency_key': 'read_race_123'})
            return snapshot

        with patch.object(variant_module, 'approval_snapshot', side_effect=publish_after_approval_read):
            result = self.room.variant(variant['id'])
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['publication_progress']['active'], 0)
        self.assertEqual(self.room.variant(variant['id'])['publication_progress']['active'], 1)

    def test_variant_list_reads_parent_and_variants_in_one_snapshot(self):
        variant = self.make_approved('x')
        original = self.room._bulletin
        changed = []

        def edit_after_parent_read(conn, bulletin_id):
            bulletin = original(conn, bulletin_id)
            if not changed:
                changed.append(True)
                self.room.save_bulletin(bulletin_id, {
                    'revision': self.bulletin['revision'], 'title': 'Tiêu đề mới'})
            return bulletin

        with patch.object(self.room, '_bulletin', side_effect=edit_after_parent_read):
            result = self.room.variants(self.bulletin['id'])
        self.assertEqual(result[0]['id'], variant['id'])
        self.assertEqual(result[0]['status'], 'approved')
        self.assertFalse(result[0]['needs_update'])
        self.assertTrue(self.room.variant(variant['id'])['needs_update'])

    def test_bulletin_stats_use_one_snapshot_during_publication(self):
        variant = self.make_approved('x')
        original_connection = self.room.connection
        inserted = []
        errors = []

        @contextmanager
        def intercepted_connection():
            with original_connection() as conn:
                def before_statement(sql):
                    if 'SELECT COUNT(DISTINCT v.bulletin_id)' in sql and not inserted:
                        inserted.append(True)
                        try:
                            self.room.record_publication(variant['id'], {
                                'revision': variant['revision'], 'position': 0,
                                'url': 'https://x.com/test/status/123456', 'idempotency_key': 'stats_race_123'})
                        except Exception as exc:
                            errors.append(exc)
                conn.set_trace_callback(before_statement)
                yield conn

        with patch.object(self.room, 'connection', side_effect=intercepted_connection):
            stats = self.room.bulletin_stats()
        self.assertEqual(errors, [])
        self.assertEqual(inserted, [True])
        self.assertEqual((stats['recorded_posts'], stats['recorded_bulletins']), (0, 0))
        self.assertEqual(self.room.bulletin_stats()['recorded_posts'], 1)

    def test_publication_list_is_consistent_during_correction(self):
        variant = self.make_approved('x')
        publication = self.room.record_publication(variant['id'], {
            'revision': variant['revision'], 'position': 0,
            'url': 'https://x.com/test/status/123456', 'idempotency_key': 'list_race_123'})
        current = self.room.variant(variant['id'])
        original_connection = self.room.connection
        corrected = []
        errors = []

        @contextmanager
        def intercepted_connection():
            with original_connection() as conn:
                def before_statement(sql):
                    if 'SELECT * FROM publication_events WHERE publication_id=' in sql and not corrected:
                        corrected.append(True)
                        try:
                            self.room.correct_publication(publication['id'], {
                                'revision': current['revision'], 'reason': 'Hủy liên kết thử', 'url': ''})
                        except Exception as exc:
                            errors.append(exc)
                conn.set_trace_callback(before_statement)
                yield conn

        with patch.object(self.room, 'connection', side_effect=intercepted_connection):
            records = self.room.publications(variant['id'])
        self.assertEqual(errors, [])
        self.assertEqual(corrected, [True])
        self.assertEqual(records[0]['active'], 1)
        self.assertEqual([event['action'] for event in records[0]['events']], ['reported'])
        self.assertEqual(self.room.publications(variant['id'])[0]['active'], 0)

    def test_correction_rejects_non_string_url_without_cancelling_publication(self):
        variant = self.make_approved('x')
        publication = self.room.record_publication(variant['id'], {
            'revision': variant['revision'], 'position': 0,
            'url': 'https://x.com/test/status/123456', 'idempotency_key': 'invalid_correction_123'})
        current = self.room.variant(variant['id'])
        before = self.room.publications(variant['id'])
        for invalid in (None, False, 0, [], {}):
            with self.subTest(url=invalid), self.assertRaises(ValidationError):
                self.room.correct_publication(publication['id'], {
                    'revision': current['revision'], 'reason': 'Kiểm tra URL', 'url': invalid})
            self.assertEqual(self.room.publications(variant['id']), before)
            self.assertEqual(self.room.variant(variant['id']), current)

    def test_preview_reads_variant_and_parent_in_one_snapshot(self):
        variant = self.make_approved('threads')
        with self.room.connection() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
        original = self.room._variant
        observed = []

        def concurrent_remove(conn, variant_id):
            selected = original(conn, variant_id)
            observed.append(conn.in_transaction)
            self.room.change_bulletin_items(self.bulletin['id'], {
                'revision': self.bulletin['revision'], 'remove_item_id': self.bulletin['items'][1]['id']})
            return selected

        with patch.object(self.room, '_variant', side_effect=concurrent_remove):
            preview = self.room.preview_variant(variant['id'])
        self.assertEqual(observed, [True])
        self.assertTrue(preview['valid'])
        self.assertEqual(preview['posts'][0]['item_ids'], [item['id'] for item in self.bulletin['items']])
        self.assertEqual(len(self.room.bulletin(self.bulletin['id'])['items']), 1)

    def test_split_reads_variant_and_parent_in_one_snapshot(self):
        variant = self.make_approved('threads')
        with self.room.connection() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
        original = self.room._locked_variant
        observed = []

        def concurrent_remove(conn, variant_id, revision):
            selected = original(conn, variant_id, revision)
            observed.append(conn.in_transaction)
            self.room.change_bulletin_items(self.bulletin['id'], {
                'revision': self.bulletin['revision'], 'remove_item_id': self.bulletin['items'][1]['id']})
            return selected

        with patch.object(self.room, '_locked_variant', side_effect=concurrent_remove):
            result = self.room.split_variant(variant['id'], {'revision': variant['revision']})
        self.assertEqual(observed, [True])
        self.assertTrue(result['preview']['valid'])
        self.assertEqual(result['preview']['posts'][0]['item_ids'], [item['id'] for item in self.bulletin['items']])
        with self.assertRaises(Conflict):
            self.room.save_variant(variant['id'], {'revision': variant['revision'], 'segments': result['segments']})

    def test_clone_preserves_all_text_when_parent_loses_an_item(self):
        variant = self.make_approved('x', two=True)
        record = self.room.record_publication(variant['id'], {'revision': variant['revision'], 'position': 0,
            'url': 'https://x.com/test/status/789', 'idempotency_key': 'clone_test_789'})
        current = self.room.variant(variant['id'])
        changed = self.room.change_bulletin_items(self.bulletin['id'], {'revision': self.bulletin['revision'],
            'remove_item_id': self.bulletin['items'][1]['id']})
        clone = self.room.clone_variant(variant['id'], {'revision': current['revision']})
        self.assertEqual([s['text'] for s in clone['segments']], [s['text'] for s in variant['segments']])
        self.assertEqual(clone['segments'][1]['item_ids'], [])
        self.assertTrue(clone['attribution_review_required'])
        with self.assertRaises(ValidationError):
            self.room.approve_variant(clone['id'], {'revision': clone['revision']})
        with self.assertRaisesRegex(ValidationError, 'kiểm tra lại'):
            self.room.save_variant(clone['id'], {'revision': clone['revision']})
        item = changed['items'][0]
        reassigned = [{**segment, 'item_ids': [item['id']],
                       'source_ids': [item['sources'][0]['source_id']]} for segment in clone['segments']]
        saved = self.room.save_variant(clone['id'], {'revision': clone['revision'], 'segments': reassigned,
                                                      'attribution_reviewed': True})
        self.assertFalse(saved.get('attribution_review_required', False))
        self.assertEqual([s['text'] for s in saved['segments']], [s['text'] for s in variant['segments']])
        self.assertEqual(self.room.publications(variant['id'])[0]['id'], record['id'])
        archived = self.room.export_variant(variant['id'], archive=True)
        self.assertEqual([item['id'] for item in archived['items']], [item['id'] for item in self.bulletin['items']])
        self.assertEqual(archived['items'][1]['sources'][0]['url'], self.bulletin['items'][1]['sources'][0]['url'])
        self.assertEqual(archived['rendered_posts'][1]['text'], archived['posts'][1])
        self.assertTrue(all(archived['checks'].values()))
        with self.assertRaises(Conflict):
            self.room.preview_variant(variant['id'])

    def test_clone_requires_review_when_a_selected_source_was_removed(self):
        item = self.bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(self.bulletin['id'], item['id'], {
            'bulletin_revision': self.bulletin['revision'], 'revision': item['revision'],
            'add_source': {'url': 'https://example.org/second', 'title': 'Nguồn thứ hai', 'summary': 'Ghi chú'}})
        item = bulletin['items'][0]
        source_id = item['sources'][1]['source_id']
        variant = self.room.create_variant(bulletin['id'], {'bulletin_revision': bulletin['revision'],
            'platform': 'facebook', 'account_label': 'Trang thử'})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
            'segments': [{'text': 'Giữ nguyên đoạn này.', 'item_ids': [item['id']], 'source_ids': [source_id]}]})
        self.room.save_bulletin_item(bulletin['id'], item['id'], {'bulletin_revision': bulletin['revision'],
            'revision': item['revision'], 'remove_source_id': source_id})
        current = self.room.variant(variant['id'])
        clone = self.room.clone_variant(variant['id'], {'revision': current['revision']})
        self.assertTrue(clone['attribution_review_required'])
        self.assertEqual(clone['segments'][0]['text'], 'Giữ nguyên đoạn này.')
        self.assertEqual(clone['segments'][0]['item_ids'], [item['id']])
        self.assertEqual(clone['segments'][0]['source_ids'], [])
        with self.assertRaises(ValidationError):
            self.room.save_variant(clone['id'], {'revision': clone['revision'], 'attribution_reviewed': True})

    def test_noop_saves_do_not_revoke_approval(self):
        variant = self.make_approved('threads')
        same_bulletin = self.room.save_bulletin(self.bulletin['id'], {'revision': self.bulletin['revision']})
        self.assertEqual(same_bulletin['revision'], self.bulletin['revision'])
        item = same_bulletin['items'][0]
        same_item = self.room.save_bulletin_item(same_bulletin['id'], item['id'], {
            'bulletin_revision': same_bulletin['revision'], 'revision': item['revision'], 'verified': item['verified']})
        self.assertEqual(same_item['revision'], same_bulletin['revision'])
        same_variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
            'segments': variant['segments'], 'checks': variant['checks']})
        self.assertEqual(same_variant['revision'], variant['revision'])
        self.assertEqual(same_variant['status'], 'approved')
        self.assertTrue(self.room.export_variant(variant['id'])['posts'])

    def test_competing_edit_and_approval_have_exactly_one_winner(self):
        variant = self.room.create_variant(self.bulletin['id'], {'platform': 'facebook',
            'account_label': 'Trang thử', 'bulletin_revision': self.bulletin['revision']})
        segment = {'text': 'Nội dung đã biên tập.', 'item_ids': [self.bulletin['items'][0]['id']]}
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'], 'segments': [segment]})
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'],
                                                          'checks': {key: True for key in CHECKS}})
        barrier = threading.Barrier(2)

        def attempt(operation):
            barrier.wait(timeout=5)
            try:
                if operation == 'approve':
                    self.room.approve_variant(variant['id'], {'revision': variant['revision']})
                else:
                    self.room.save_variant(variant['id'], {'revision': variant['revision'],
                        'segments': [{**segment, 'text': 'Nội dung đã thay đổi.'}]})
                return operation
            except Conflict:
                return 'conflict'

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, ('approve', 'edit')))
        self.assertEqual(outcomes.count('conflict'), 1)
        current = self.room.variant(variant['id'])
        if current['status'] == 'approved':
            self.assertIn('Nội dung đã biên tập.', self.room.export_variant(variant['id'])['posts'][0])
        else:
            self.assertEqual(current['segments'][0]['text'], 'Nội dung đã thay đổi.')
            with self.assertRaises(ValidationError):
                self.room.export_variant(variant['id'])

    def test_competing_variant_saves_have_one_winner_and_no_lost_update(self):
        variant = self.room.create_variant(self.bulletin['id'], {'platform': 'x',
            'account_label': 'Kênh thử', 'bulletin_revision': self.bulletin['revision']})
        segment = {'text': 'Nội dung ban đầu.', 'item_ids': [self.bulletin['items'][0]['id']]}
        variant = self.room.save_variant(variant['id'], {'revision': variant['revision'], 'segments': [segment]})
        barrier = threading.Barrier(2)

        def attempt(text):
            barrier.wait(timeout=5)
            try:
                result = self.room.save_variant(variant['id'], {'revision': variant['revision'],
                    'expected_bulletin_revision': self.bulletin['revision'],
                    'segments': [{**segment, 'text': text}]})
                return ('saved', text, result)
            except Conflict:
                return ('conflict', text, None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ('Bản sửa thứ nhất.', 'Bản sửa thứ hai.')))
        self.assertEqual(sorted(result[0] for result in results), ['conflict', 'saved'])
        winner = next(result for result in results if result[0] == 'saved')
        reopened = Newsroom(self.room.data_dir).variant(variant['id'])
        self.assertEqual(reopened, winner[2])
        self.assertEqual(reopened['segments'][0]['text'], winner[1])
        self.assertEqual(reopened['revision'], variant['revision'] + 1)

    def test_competing_edit_and_record_keep_approval_and_publication_consistent(self):
        # Each pair uses the same revision, as two editor tabs would.
        for index in range(4):
            with self.subTest(attempt=index):
                variant = self.make_approved('x')
                approved = self.room.export_variant(variant['id'], archive=True)
                barrier = threading.Barrier(2)
                edited = [{**variant['segments'][0], 'text': f'Nội dung sửa thử {index}.'}]

                def attempt(operation):
                    barrier.wait(timeout=5)
                    try:
                        if operation == 'edit':
                            self.room.save_variant(variant['id'], {
                                'revision': variant['revision'], 'segments': edited})
                        else:
                            self.room.record_publication(variant['id'], {
                                'revision': variant['revision'], 'position': 0,
                                'url': f'https://x.com/test/status/{987650 + index}',
                                'idempotency_key': f'edit_record_{index}'})
                        return operation
                    except Conflict:
                        return 'conflict'

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(attempt, ('edit', 'record')))
                self.assertEqual(outcomes.count('conflict'), 1)
                current = self.room.variant(variant['id'])
                publications = self.room.publications(variant['id'])
                if 'record' in outcomes:
                    self.assertEqual(len(publications), 1)
                    self.assertTrue(publications[0]['active'])
                    self.assertEqual(current['segments'], variant['segments'])
                    self.assertIsNotNone(current['locked_at'])
                    self.assertEqual(self.room.export_variant(variant['id'], archive=True), approved)
                else:
                    self.assertIn('edit', outcomes)
                    self.assertEqual(publications, [])
                    self.assertEqual(current['segments'], edited)
                    self.assertEqual(current['status'], 'draft')
                    self.assertIsNone(current['locked_at'])
                    with self.assertRaises(ValidationError):
                        self.room.export_variant(variant['id'])

    def test_parent_edit_and_record_serialize_in_both_orders(self):
        for first_operation in ('edit', 'record'):
            with self.subTest(first_operation=first_operation):
                variant = self.make_approved('x')
                approved = self.room.export_variant(variant['id'], archive=True)
                bulletin = self.room.bulletin(self.bulletin['id'])
                locked = threading.Event()
                release = threading.Event()
                queued = threading.Event()
                thread_state = threading.local()
                method_name = '_locked_bulletin' if first_operation == 'edit' else '_locked_variant'
                original = getattr(self.room, method_name)
                original_connection = self.room.connection

                @contextmanager
                def traced_connection():
                    with original_connection() as conn:
                        if getattr(thread_state, 'second', False):
                            conn.set_trace_callback(lambda sql: queued.set() if sql == 'BEGIN IMMEDIATE' else None)
                        yield conn

                def hold_transaction(*args):
                    result = original(*args)
                    locked.set()
                    if not release.wait(10):
                        raise AssertionError('Transaction was not released')
                    return result

                def attempt(operation, signal=False):
                    thread_state.second = signal
                    if operation == 'edit':
                        return self.room.save_bulletin(bulletin['id'], {
                            'revision': bulletin['revision'], 'title': f'Bản tin sửa khi {first_operation}'})
                    return self.room.record_publication(variant['id'], {
                        'revision': variant['revision'], 'position': 0,
                        'url': f'https://x.com/test/status/{1001 if first_operation == "edit" else 1002}',
                        'idempotency_key': f'parent_race_{first_operation}'})

                with patch.object(self.room, method_name, side_effect=hold_transaction), \
                     patch.object(self.room, 'connection', side_effect=traced_connection):
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        first = pool.submit(attempt, first_operation)
                        try:
                            self.assertTrue(locked.wait(10), 'First transaction did not acquire its lock')
                            second_operation = 'record' if first_operation == 'edit' else 'edit'
                            second = pool.submit(attempt, second_operation, True)
                            self.assertTrue(queued.wait(10), 'Second transaction did not start')
                        finally:
                            release.set()
                        first.result(timeout=10)
                        if first_operation == 'edit':
                            with self.assertRaises(Conflict):
                                second.result(timeout=10)
                        else:
                            second.result(timeout=10)

                current = self.room.variant(variant['id'])
                publications = self.room.publications(variant['id'])
                self.assertEqual(self.room.bulletin(bulletin['id'])['revision'], bulletin['revision'] + 1)
                if first_operation == 'edit':
                    self.assertEqual(publications, [])
                    self.assertEqual(current['status'], 'draft')
                    self.assertIsNone(current['locked_at'])
                    self.assertTrue(current['needs_update'])
                    self.assertTrue(all(value is False for value in current['checks'].values()))
                    with self.assertRaises(ValidationError):
                        self.room.export_variant(variant['id'])
                else:
                    self.assertEqual(len(publications), 1)
                    self.assertTrue(publications[0]['active'])
                    self.assertEqual(publications[0]['url'], 'https://x.com/test/status/1002')
                    self.assertEqual(publications[0]['approval_id'], approved['approval_id'])
                    self.assertIsNotNone(current['locked_at'])
                    self.assertEqual(current['status'], 'recorded')
                    self.assertEqual(self.room.export_variant(variant['id'], archive=True), approved)
                self.bulletin = self.room.bulletin(bulletin['id'])

    def test_record_separate_segments_retry_and_immutable_after_correction(self):
        variant = self.make_approved('x', two=True)
        data = {'revision': variant['revision'], 'position': 0, 'url': 'https://x.com/test/status/123',
                'idempotency_key': 'test_key_123'}
        first = self.room.record_publication(variant['id'], data)
        self.assertEqual(self.room.record_publication(variant['id'], data)['id'], first['id'])
        with self.assertRaises(Conflict):
            self.room.record_publication(variant['id'], {**data, 'url': 'https://x.com/test/status/456'})
        current = self.room.variant(variant['id'])
        self.assertEqual(current['status'], 'partially_recorded')
        stats = self.room.bulletin_stats()
        self.assertEqual((stats['bulletins'], stats['variants'], stats['recorded_bulletins'], stats['recorded_posts']), (1, 1, 1, 1))
        with self.assertRaises(Conflict) as caught:
            self.room.record_publication(variant['id'], {'revision': current['revision'], 'position': 1,
                'url': 'https://twitter.com/another_name/status/123?s=20', 'idempotency_key': 'alias_key_123'})
        self.assertEqual(caught.exception.target, {'kind': 'publication', 'bulletin_id': self.bulletin['id'],
            'variant_id': variant['id'], 'publication_id': first['id'], 'position': 0})
        with self.assertRaises(ValidationError):
            self.room.correct_publication(first['id'], {'revision': current['revision'],
                'reason': 'Thử alias cùng bài', 'url': 'https://x.com/renamed/status/123?s=20'})
        self.room.save_bulletin(self.bulletin['id'], {'revision': self.bulletin['revision'], 'title': 'Bản sửa'})
        second = self.room.record_publication(variant['id'], {'revision': current['revision'], 'position': 1,
            'url': 'https://twitter.com/test/status/456', 'idempotency_key': 'test_key_456'})
        self.assertEqual(second['url'], 'https://x.com/test/status/456')
        current = self.room.variant(variant['id'])
        self.assertEqual(current['status'], 'recorded')
        before = self.room.publications(variant['id'])
        with self.assertRaises(Conflict) as caught:
            self.room.correct_publication(first['id'], {'revision': current['revision'],
                'reason': 'Nhập nhầm liên kết', 'url': 'https://x.com/renamed/status/456'})
        self.assertEqual(caught.exception.target, {'kind': 'publication', 'bulletin_id': self.bulletin['id'],
            'variant_id': variant['id'], 'publication_id': second['id'], 'position': 1})
        self.assertEqual(self.room.publications(variant['id']), before)
        self.assertEqual(self.room.variant(variant['id']), current)
        self.assertEqual(self.room.bulletin_stats()['recorded_posts'], 2)
        with self.assertRaises(Conflict):
            self.room.save_variant(variant['id'], {'revision': current['revision']})
        self.room.correct_publication(first['id'], {'revision': current['revision'], 'reason': 'Nhập nhầm liên kết'})
        current = self.room.variant(variant['id'])
        self.assertEqual(current['status'], 'partially_recorded')
        self.assertEqual(self.room.bulletin_stats()['recorded_posts'], 1)
        self.assertIsNotNone(current['locked_at'])
        with self.assertRaises(Conflict):
            self.room.save_variant(variant['id'], {'revision': current['revision']})

    def test_correction_key_cannot_collide_with_client_recording_key(self):
        variant = self.make_approved('x', two=True)
        first = self.room.record_publication(variant['id'], {
            'revision': variant['revision'], 'position': 0,
            'url': 'https://x.com/test/status/101', 'idempotency_key': 'first_record_101'})
        current = self.room.variant(variant['id'])
        client_key = f"correction_{first['id']}_{current['revision'] + 1}"
        second = self.room.record_publication(variant['id'], {
            'revision': current['revision'], 'position': 1,
            'url': 'https://x.com/test/status/102', 'idempotency_key': client_key})
        current = self.room.variant(variant['id'])
        result = self.room.correct_publication(first['id'], {
            'revision': current['revision'], 'reason': 'Sửa liên kết đã nhập nhầm',
            'url': 'https://x.com/test/status/103'})
        records = self.room.publications(variant['id'])
        self.assertEqual([row['id'] for row in records if row['active']],
                         [second['id'], result['replacement_id']])
        self.assertEqual(self.room.bulletin_stats()['recorded_posts'], 2)
        self.assertEqual(records[0]['events'][-1]['action'], 'corrected')
        self.assertEqual(records[-1]['idempotency_key'], f"correction:{first['id']}:{current['revision']}")
        retried = self.room.record_publication(variant['id'], {
            'revision': current['revision'], 'position': 1,
            'url': 'https://x.com/test/status/102', 'idempotency_key': client_key})
        self.assertEqual(retried['id'], second['id'])
        with self.assertRaises(ValidationError):
            self.room.record_publication(variant['id'], {
                'revision': current['revision'], 'position': 1,
                'url': 'https://x.com/test/status/104', 'idempotency_key': records[-1]['idempotency_key']})

    def test_cancel_all_preserves_lock_and_history_and_can_record_again(self):
        variant = self.make_approved('x', two=True)
        records = []
        for position in range(2):
            current = self.room.variant(variant['id'])
            records.append(self.room.record_publication(variant['id'], {'revision': current['revision'],
                'position': position, 'url': f'https://x.com/test/status/{100 + position}',
                'idempotency_key': f'cancel_test_{position}'}))
        locked_at = self.room.variant(variant['id'])['locked_at']
        for position, record in enumerate(records):
            current = self.room.variant(variant['id'])
            self.room.correct_publication(record['id'], {'revision': current['revision'], 'reason': 'Nhập nhầm liên kết'})
            current = self.room.variant(variant['id'])
            self.assertEqual(current['status'], 'partially_recorded' if position == 0 else 'approved')
            self.assertEqual(current['publication_progress'], {'active': 1 - position, 'total': 2})
            self.assertEqual(current['locked_at'], locked_at)
        with self.assertRaises(Conflict):
            self.room.save_variant(variant['id'], {'revision': current['revision']})
        history = self.room.publications(variant['id'])
        self.assertEqual([event['action'] for event in history[0]['events']], ['reported', 'cancelled'])
        with self.room.connection() as conn:
            conn.execute("UPDATE content_variants SET status='partially_recorded' WHERE id=?", (variant['id'],))
        restarted = Newsroom(Path(self.temp.name))
        current = restarted.variant(variant['id'])
        self.assertEqual(current['publication_progress'], {'active': 0, 'total': 2})
        replacement = restarted.record_publication(variant['id'], {'revision': current['revision'], 'position': 0,
            'url': 'https://x.com/test/status/100', 'idempotency_key': 'cancel_test_retry'})
        self.assertNotEqual(replacement['id'], records[0]['id'])
        self.assertEqual(restarted.variant(variant['id'])['publication_progress'], {'active': 1, 'total': 2})

    def test_policy_change_after_partial_recording_preserves_snapshot(self):
        variant = self.make_approved('x', two=True)
        archive = self.room.export_variant(variant['id'], archive=True)
        self.room.record_publication(variant['id'], {'revision': variant['revision'], 'position': 0,
            'url': 'https://x.com/test/status/301', 'idempotency_key': 'policy_partial_1'})
        self.room.save_bulletin(self.bulletin['id'], {'revision': self.bulletin['revision'], 'title': 'Bản sửa'})
        with patch('newsroom.variants.POLICY_VERSION', 'future-policy'):
            current = self.room.variant(variant['id'])
            with self.assertRaises(ValidationError):
                self.room.export_variant(variant['id'])
            self.assertEqual(self.room.export_variant(variant['id'], archive=True), archive)
            self.room.record_publication(variant['id'], {'revision': current['revision'], 'position': 1,
                'url': 'https://x.com/test/status/302', 'idempotency_key': 'policy_partial_2'})
            self.assertEqual(self.room.variant(variant['id'])['status'], 'recorded')
            self.assertEqual(self.room.export_variant(variant['id'], archive=True), archive)

    def test_social_url_validation_and_manual_metrics(self):
        for url in ('https://x.com/', 'https://x.com/person', 'https://x.com.evil.example/person/status/123',
                    'https://user:pass@x.com/a/status/123', 'http://x.com/a/status/123'):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                normalize_post_url('x', url)
        self.assertEqual(normalize_post_url('threads', 'https://threads.net/@user/post/abc'),
                         'https://www.threads.com/@user/post/abc')
        self.assertEqual(normalize_post_url('x', 'https://twitter.com/user/status/123?s=20'),
                         'https://x.com/user/status/123')
        variant = self.make_approved('facebook')
        record = self.room.record_publication(variant['id'], {'revision': variant['revision'], 'position': 0,
            'url': 'https://www.facebook.com/page/posts/100', 'idempotency_key': 'facebook_100'})
        metric = self.room.save_publication_metrics(record['id'], {'observed_at': '2026-11-03T10:00:00+07:00',
                                                                    'likes': 0})
        self.assertIsNone(metric['views'])
        self.assertEqual(metric['likes'], 0)

    def test_threads_shorthand_and_permalink_share_post_identity(self):
        self.assertEqual(normalize_post_url('threads', 'https://threads.net/t/AbC_12-3/?ref=test'),
                         'https://www.threads.com/t/AbC_12-3')
        # Characterization: the full permalink has a broader pattern than /t/.
        # Acceptance here does not establish that Meta recognizes the URL.
        self.assertEqual(normalize_post_url('threads', 'https://threads.net/@user/post/a%2Fb'),
                         'https://www.threads.com/@user/post/a%2Fb')
        for invalid in ('https://threads.com/t/', 'https://threads.com/t/abc/extra',
                        'https://threads.com.evil.example/t/abc', 'https://threads.com/t/a%2Fb'):
            with self.subTest(url=invalid), self.assertRaises(ValidationError):
                normalize_post_url('threads', invalid)
        for index, (first_path, second_path) in enumerate((
            ('/t/AbC_12-3', '/@example/post/AbC_12-3'),
            ('/@example/post/XyZ_456', '/t/XyZ_456'))):
            first = self.make_approved('threads')
            second = self.make_approved('threads')
            record = self.room.record_publication(first['id'], {'revision': first['revision'], 'position': 0,
                'url': 'https://threads.com' + first_path, 'idempotency_key': f'thread_first_{index}'})
            with self.assertRaises(Conflict) as caught:
                self.room.record_publication(second['id'], {'revision': second['revision'], 'position': 0,
                    'url': 'https://threads.net' + second_path, 'idempotency_key': f'thread_second_{index}'})
            self.assertEqual(caught.exception.target['publication_id'], record['id'])
            self.assertEqual(self.room.publications(second['id']), [])

    def test_threads_alias_correction_conflicts_and_release_preserve_history(self):
        first = self.make_approved('threads')
        second = self.make_approved('threads')
        one = self.room.record_publication(first['id'], {'revision': first['revision'], 'position': 0,
            'url': 'https://threads.com/t/First_123', 'idempotency_key': 'thread_correction_one'})
        two = self.room.record_publication(second['id'], {'revision': second['revision'], 'position': 0,
            'url': 'https://threads.com/@other/post/Second_456', 'idempotency_key': 'thread_correction_two'})
        current = self.room.variant(first['id'])
        with self.assertRaises(ValidationError):
            self.room.correct_publication(one['id'], {'revision': current['revision'], 'reason': 'Kiểm tra alias',
                'url': 'https://threads.net/@another/post/First_123'})
        with self.assertRaises(Conflict) as caught:
            self.room.correct_publication(one['id'], {'revision': current['revision'], 'reason': 'Kiểm tra trùng',
                'url': 'https://threads.net/t/Second_456'})
        self.assertEqual(caught.exception.target['publication_id'], two['id'])
        unchanged = self.room.publications(first['id'])
        self.assertEqual(len(unchanged), 1)
        self.assertEqual(unchanged[0]['active'], 1)
        self.assertEqual([event['action'] for event in unchanged[0]['events']], ['reported'])
        replacement = self.room.correct_publication(one['id'], {'revision': current['revision'], 'reason': 'Sửa URL nhầm',
            'url': 'https://threads.com/t/Third_789'})
        history = self.room.publications(first['id'])
        self.assertEqual([record['active'] for record in history], [0, 1])
        self.assertEqual([event['action'] for event in history[0]['events']], ['reported', 'corrected'])
        current = self.room.variant(first['id'])
        self.room.correct_publication(replacement['replacement_id'], {'revision': current['revision'], 'reason': 'Hủy ghi nhận'})
        third = self.make_approved('threads')
        reused = self.room.record_publication(third['id'], {'revision': third['revision'], 'position': 0,
            'url': 'https://threads.net/@account/post/Third_789', 'idempotency_key': 'thread_correction_reuse'})
        self.assertEqual(reused['active'], 1)
        self.assertTrue(self.room.variant(first['id'])['locked_at'])

    def test_three_platform_correction_preserves_each_publication_metrics_and_lock(self):
        cases = (
            ('facebook', 'https://www.facebook.com/page/posts/1001', 'https://www.facebook.com/page/posts/1002'),
            ('threads', 'https://threads.net/@page/post/abc1001', 'https://threads.net/@page/post/abc1002'),
            ('x', 'https://x.com/page/status/1001', 'https://x.com/page/status/1002'),
        )
        for platform, old_url, new_url in cases:
            with self.subTest(platform=platform):
                variant = self.make_approved(platform)
                record = self.room.record_publication(variant['id'], {'revision': variant['revision'],
                    'position': 0, 'url': old_url, 'idempotency_key': f'platform_record_{platform}'})
                self.room.save_publication_metrics(record['id'], {
                    'observed_at': '2026-11-03T10:00:00+07:00', 'views': 0})
                archive = self.room.export_variant(variant['id'], archive=True)
                current = self.room.variant(variant['id'])
                result = self.room.correct_publication(record['id'], {'revision': current['revision'],
                    'url': new_url, 'reason': 'Sửa liên kết nhập nhầm'})
                records = self.room.publications(variant['id'])
                self.assertEqual([row['active'] for row in records], [0, 1])
                self.assertEqual(records[1]['id'], result['replacement_id'])
                self.assertEqual([event['action'] for event in records[0]['events']], ['reported', 'corrected'])
                self.assertEqual(json.loads(records[0]['metrics'][0]['payload'])['views'], 0)
                self.assertEqual(records[1]['metrics'], [])
                current = self.room.variant(variant['id'])
                self.assertTrue(current['locked_at'])
                with self.assertRaises(Conflict):
                    self.room.save_variant(current['id'], {'revision': current['revision']})
                self.assertEqual(self.room.publications(variant['id']), records)
                reopened = Newsroom(Path(self.temp.name))
                self.assertEqual(reopened.publications(variant['id']), records)
                self.assertEqual(reopened.export_variant(variant['id'], archive=True), archive)

    def test_platform_metrics_keep_optional_values_and_validate_without_partial_writes(self):
        variant = self.make_approved('x')
        record = self.room.record_publication(variant['id'], {'revision': variant['revision'], 'position': 0,
            'url': 'https://x.com/test/status/900', 'idempotency_key': 'metrics_test_900'})
        at = '2026-11-03T10:00:00+07:00'
        old = self.room.save_publication_metrics(record['id'], {'observed_at': at, 'shares': 3})
        self.assertNotIn('reposts', old)
        new = self.room.save_publication_metrics(record['id'], {'observed_at': at,
            'replies': 0, 'reposts': 8, 'quotes': None})
        self.assertEqual((new['replies'], new['reposts'], new['quotes']), (0, 8, None))
        for value in (-1, True, 1.5, '3', 1000000001):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.room.save_publication_metrics(record['id'], {'observed_at': at, 'reposts': value})
        metrics = self.room.publications(variant['id'])[0]['metrics']
        self.assertEqual(len(metrics), 2)
        self.assertEqual(json.loads(metrics[0]['payload'])['shares'], 3)
        self.assertEqual(json.loads(metrics[1]['payload'])['reposts'], 8)

    def test_metric_retry_key_is_idempotent_and_rejects_changed_payload(self):
        variant = self.make_approved('x')
        record = self.room.record_publication(variant['id'], {'revision': variant['revision'], 'position': 0,
            'url': 'https://x.com/test/status/901', 'idempotency_key': 'metrics_post_901'})
        payload = {'observed_at': '2026-11-03T10:00:00+07:00', 'views': 0,
                   'reposts': 2, 'idempotency_key': 'metrics_retry_901'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.room.save_publication_metrics(record['id'], payload), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.room.publications(variant['id'])[0]['metrics']), 1)
        with self.assertRaises(Conflict):
            self.room.save_publication_metrics(record['id'], {**payload, 'reposts': 3})
        self.assertEqual(len(self.room.publications(variant['id'])[0]['metrics']), 1)
        with self.assertRaises(ValidationError):
            self.room.save_publication_metrics(record['id'], {**payload, 'idempotency_key': 'bad'})

    def test_reported_and_observed_times_use_utc_and_retry_legacy_offsets(self):
        variant = self.make_approved('x')
        data = {'revision': variant['revision'], 'position': 0, 'url': 'https://x.com/test/status/902',
                'idempotency_key': 'time_retry_902', 'reported_at': '2026-11-03T10:00:00+07:00'}
        record = self.room.record_publication(variant['id'], data)
        self.assertEqual(record['reported_at'], '2026-11-03T03:00:00+00:00')
        self.assertEqual(self.room.record_publication(variant['id'], {**data, 'reported_at': '2026-11-03T03:00:00Z'})['id'], record['id'])
        metric_data = {'observed_at': '2026-11-03T10:00:00+07:00', 'views': 7,
                       'idempotency_key': 'metric_time_902'}
        metric = self.room.save_publication_metrics(record['id'], metric_data)
        self.assertEqual(metric['observed_at'], '2026-11-03T03:00:00+00:00')
        self.assertEqual(self.room.save_publication_metrics(record['id'], {**metric_data,
            'observed_at': '2026-11-03T03:00:00Z'}), metric)
        # Simulate rows created before UTC normalization, including the original request hash.
        import hashlib
        from newsroom.publications import _json
        legacy_time = '2026-11-03T10:00:00+07:00'
        legacy_request = {'variant_id': variant['id'], 'position': 0, 'url': data['url'], 'reported_at': legacy_time}
        with self.room.connection() as conn:
            conn.execute('UPDATE publications SET reported_at=?, request_hash=? WHERE id=?',
                (legacy_time, hashlib.sha256(_json(legacy_request).encode()).hexdigest(), record['id']))
            conn.execute('UPDATE publication_metrics SET observed_at=? WHERE id=?', (legacy_time, metric['id']))
        retried = self.room.record_publication(variant['id'], data)
        self.assertEqual(retried['reported_at'], legacy_time)
        self.assertEqual(self.room.record_publication(variant['id'], {**data,
            'reported_at': '2026-11-03T03:00:00Z'})['id'], record['id'])
        retried_metric = self.room.save_publication_metrics(record['id'], metric_data)
        self.assertEqual(retried_metric['observed_at'], legacy_time)
        self.assertEqual(retried_metric['id'], metric['id'])
        self.assertEqual(self.room.save_publication_metrics(record['id'], {**metric_data,
            'observed_at': '2026-11-03T03:00:00Z'})['id'], metric['id'])
        with self.assertRaises(Conflict):
            self.room.record_publication(variant['id'], {**data, 'reported_at': '2026-11-03T11:00:00+07:00'})
        with self.assertRaises(ValidationError):
            self.room.save_publication_metrics(record['id'], {**metric_data, 'observed_at': '0001-01-01T00:00:00+14:00'})

    def test_policy_change_keeps_archive_but_blocks_ready_export(self):
        variant = self.make_approved('x')
        with patch('newsroom.variants.POLICY_VERSION', 'future-policy'):
            with self.assertRaises(ValidationError):
                self.room.export_variant(variant['id'])
            self.assertTrue(self.room.export_variant(variant['id'], archive=True)['archive'])

    def test_older_approvals_are_stale_but_archive_remains_available(self):
        for version in ('2026-11-03-v1', '2026-11-03-v2', '2026-11-04-v4'):
            with self.subTest(version=version):
                with patch('newsroom.variants.POLICY_VERSION', version):
                    variant = self.make_approved('x')
                    archive = self.room.export_variant(variant['id'], archive=True)
                self.assertTrue(self.room.variant(variant['id'])['policy_stale'])
                with self.assertRaises(ValidationError):
                    self.room.export_variant(variant['id'])
                self.assertEqual(self.room.export_variant(variant['id'], archive=True), archive)

    def test_policy_change_requires_new_checks_before_reapproval(self):
        variant = self.make_approved('threads')
        with patch('newsroom.variants.POLICY_VERSION', 'future-policy'):
            stale = self.room.variant(variant['id'])
            self.assertTrue(stale['policy_stale'])
            with self.assertRaises(ValidationError):
                self.room.approve_variant(stale['id'], {'revision': stale['revision']})
            reset = self.room.save_variant(stale['id'], {'revision': stale['revision'],
                                                          'checks': {key: True for key in CHECKS}})
            self.assertFalse(reset['policy_stale'])
            self.assertFalse(any(reset['checks'].values()))
            with self.assertRaises(ValidationError):
                self.room.approve_variant(reset['id'], {'revision': reset['revision']})
            confirmed = self.room.save_variant(reset['id'], {'revision': reset['revision'],
                                                             'checks': {key: True for key in CHECKS}})
            approved = self.room.approve_variant(confirmed['id'], {'revision': confirmed['revision']})
            self.assertEqual(approved['status'], 'approved')

    def test_renderer_change_also_requires_review_before_reapproval(self):
        variant = self.make_approved('x')
        with patch('newsroom.variants.RENDERER_VERSION', 'future-renderer'):
            stale = self.room.variant(variant['id'])
            self.assertTrue(stale['policy_stale'])
            with self.assertRaises(ValidationError):
                self.room.approve_variant(stale['id'], {'revision': stale['revision']})
            reset = self.room.save_variant(stale['id'], {'revision': stale['revision']})
            self.assertFalse(any(reset['checks'].values()))


if __name__ == '__main__':
    unittest.main()
