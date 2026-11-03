import tempfile
import unittest
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
                'verification_note': 'Đã đối chiếu nguồn gốc và ngày phát hành.'})
            current = next(row for row in bulletin['items'] if row['id'] == item['id'])
            bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
                'bulletin_revision': bulletin['revision'], 'revision': current['revision'], 'verified': True})
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

    def test_format_counts_and_source_links(self):
        self.assertEqual(count_text('x', 'english text 日本語 😷 https://example.com')[0], 46)
        self.assertEqual(count_text('x', '🙋🏽👨‍🎤')[0], 4)
        self.assertEqual(count_text('threads', 'a😷')[0], 5)
        item = self.bulletin['items'][0]
        result = render_segments('x', [{'text': 'x' * 255, 'item_ids': [item['id']]}], self.bulletin)
        self.assertFalse(result['valid'])  # source URL and its label count too
        self.assertIn(item['sources'][0]['url'], result['posts'][0]['text'])

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
        self.room.save_bulletin(self.bulletin['id'], {'revision': self.bulletin['revision'], 'title': 'Bản sửa'})
        second = self.room.record_publication(variant['id'], {'revision': current['revision'], 'position': 1,
            'url': 'https://twitter.com/test/status/456', 'idempotency_key': 'test_key_456'})
        self.assertEqual(second['url'], 'https://x.com/test/status/456')
        current = self.room.variant(variant['id'])
        self.assertEqual(current['status'], 'recorded')
        with self.assertRaises(Conflict):
            self.room.save_variant(variant['id'], {'revision': current['revision']})
        self.room.correct_publication(first['id'], {'revision': current['revision'], 'reason': 'Nhập nhầm liên kết'})
        current = self.room.variant(variant['id'])
        self.assertEqual(current['status'], 'partially_recorded')
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


if __name__ == '__main__':
    unittest.main()
