import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from newsroom.publications import normalize_post_url
from newsroom.service import Conflict, Newsroom, ValidationError
from newsroom.social_formats import count_text, render_segments, split_segments
from newsroom.variants import CHECKS


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

    def test_legacy_and_variant_cannot_claim_same_facebook_post_in_either_order(self):
        legacy = self.make_approved_legacy()
        variant = self.make_approved('facebook')
        self.room.record_publication(variant['id'], {'revision': variant['revision'], 'position': 0,
            'url': 'https://www.facebook.com/page/posts/100', 'idempotency_key': 'cross_claim_100'})
        with self.assertRaises(Conflict):
            self.room.mark_published(legacy['id'], legacy['revision'], 'https://m.facebook.com/page/posts/100?ref=share')
        self.assertEqual(self.room.draft(legacy['id'])['status'], 'approved')

        legacy = self.make_approved_legacy()
        self.room.mark_published(legacy['id'], legacy['revision'], 'https://facebook.com/page/posts/200')
        another = self.make_approved('facebook')
        with self.assertRaises(Conflict):
            self.room.record_publication(another['id'], {'revision': another['revision'], 'position': 0,
                'url': 'https://m.facebook.com/page/posts/200?ref=share', 'idempotency_key': 'cross_claim_200'})
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
        self.assertEqual(count_text('threads', 'a😷')[0], 5)
        item = self.bulletin['items'][0]
        result = render_segments('x', [{'text': 'x' * 255, 'item_ids': [item['id']]}], self.bulletin)
        self.assertFalse(result['valid'])  # source URL and its label count too
        self.assertIn(item['sources'][0]['url'], result['posts'][0]['text'])

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

    def test_split_rechecks_numbering_and_keeps_sources_and_text(self):
        item = self.bulletin['items'][0]
        # Each sentence fits alone, but two do not. The last index crosses 9→10.
        sentences = [f'Câu {i}: ' + ('n' * 145) + f' 😷 https://example.com/a{i}.' for i in range(1, 11)]
        original = ' '.join(sentences)
        segments = [{'text': original, 'item_ids': [item['id']],
                     'source_ids': [item['sources'][0]['source_id']]}]
        split = split_segments('x', segments, self.bulletin)
        self.assertEqual(len(split), 10)
        self.assertEqual(' '.join(segment['text'] for segment in split), original)
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

    def test_approved_export_matches_preview_and_changes_invalidate(self):
        variant = self.make_approved('threads')
        preview = self.room.preview_variant(variant['id'])
        exported = self.room.export_variant(variant['id'])
        self.assertEqual(exported['posts'], [post['text'] for post in preview['posts']])
        self.room.save_bulletin(self.bulletin['id'], {'revision': self.bulletin['revision'], 'title': 'Đổi bản tin'})
        self.assertTrue(self.room.variant(variant['id'])['needs_update'])
        with self.assertRaises(ValidationError):
            self.room.export_variant(variant['id'])

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
        with self.assertRaises(Conflict):
            self.room.record_publication(variant['id'], {'revision': current['revision'], 'position': 1,
                'url': 'https://twitter.com/another_name/status/123?s=20', 'idempotency_key': 'alias_key_123'})
        with self.assertRaises(ValidationError):
            self.room.correct_publication(first['id'], {'revision': current['revision'],
                'reason': 'Thử alias cùng bài', 'url': 'https://x.com/renamed/status/123?s=20'})
        self.room.save_bulletin(self.bulletin['id'], {'revision': self.bulletin['revision'], 'title': 'Bản sửa'})
        second = self.room.record_publication(variant['id'], {'revision': current['revision'], 'position': 1,
            'url': 'https://twitter.com/test/status/456', 'idempotency_key': 'test_key_456'})
        self.assertEqual(second['url'], 'https://x.com/test/status/456')
        current = self.room.variant(variant['id'])
        self.assertEqual(current['status'], 'recorded')
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

    def test_policy_change_keeps_archive_but_blocks_ready_export(self):
        variant = self.make_approved('x')
        with patch('newsroom.variants.POLICY_VERSION', 'future-policy'):
            with self.assertRaises(ValidationError):
                self.room.export_variant(variant['id'])
            self.assertTrue(self.room.export_variant(variant['id'], archive=True)['archive'])

    def test_v1_approval_is_stale_under_v2_but_archive_remains_available(self):
        with patch('newsroom.variants.POLICY_VERSION', '2026-11-03-v1'):
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
