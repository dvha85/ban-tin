import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from pathlib import Path

from newsroom.service import Newsroom, Conflict, ValidationError


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.room = Newsroom(Path(self.temp.name))
        self.item = {
            'title': 'A useful new AI assistant', 'url': 'https://example.com/news/one',
            'summary': 'A brief RSS excerpt, not a full article.',
            'published_at': '2026-10-14T08:00:00+00:00', 'date_kind': 'published',
        }
        self.source = {'id': 'test', 'name': 'Example', 'url': 'https://example.com/feed'}
        self.room.ingest(self.source, [self.item])
        self.article = self.room.articles()[0]

    def tearDown(self):
        self.temp.cleanup()

    def valid_draft(self):
        draft = self.room.create_draft(self.article['id'])
        draft = self.room.save_draft(draft['id'], {
            'revision': draft['revision'], 'title': 'Trợ lý mới có ích gì cho người Việt?',
            'body': 'Đây là bản kiểm thử, không phải tin đã được xác minh. ' * 4,
            'angle': 'Giải thích lợi ích và giới hạn thực tế.',
            'page_name': 'Bàn tin thử nghiệm',
        })
        return self.room.save_draft(draft['id'], {
            'revision': draft['revision'], 'checks': {key: True for key in self.room.CHECKS},
        })

    def test_dedup_url_and_exact_title_preserve_sources(self):
        self.assertEqual(self.room.ingest(self.source, [self.item])['added'], 0)
        second = dict(self.item, url='https://other.example/story')
        self.room.ingest(dict(self.source, id='other', name='Other'), [second])
        articles = self.room.articles()
        self.assertEqual(len(articles), 1)
        self.assertEqual(len(articles[0]['sources']), 2)

    def test_future_article_state_does_not_claim_recency(self):
        timestamp = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        self.room.ingest(self.source, [{'title': 'Thông báo giả ở tương lai',
            'url': 'https://example.com/future-article', 'summary': 'Nội dung giả.',
            'published_at': timestamp, 'date_kind': 'published'}])
        article = next(row for row in self.room.state()['articles'] if row['url'] == 'https://example.com/future-article')
        self.assertEqual(article['score'], 20)
        self.assertIn('Ngày nguồn ở tương lai — cần kiểm tra', article['reasons'])
        self.assertNotIn('Nguồn có mốc thời gian trong 48 giờ', article['reasons'])

    def test_prompt_has_provenance_limits_and_untrusted_delimiter(self):
        draft = self.room.create_draft(self.article['id'])
        packet = self.room.packet(draft['id'])
        self.assertIn(self.item['url'], packet)
        self.assertIn('RSS', packet)
        self.assertIn('DỮ LIỆU NGUỒN', packet)
        self.assertIn('không', packet.lower())
        self.assertNotIn('api_key', packet.lower())

    def test_cannot_approve_empty_draft(self):
        draft = self.room.create_draft(self.article['id'])
        with self.assertRaises(ValidationError):
            self.room.approve(draft['id'], draft['revision'])

    def test_approval_requires_every_check(self):
        draft = self.valid_draft()
        draft = self.room.save_draft(draft['id'], {'revision': draft['revision'], 'checks': {}})
        with self.assertRaises(ValidationError):
            self.room.approve(draft['id'], draft['revision'])

    def test_edit_revokes_approval_and_resets_checks(self):
        draft = self.valid_draft()
        approved = self.room.approve(draft['id'], draft['revision'])
        self.assertEqual(approved['status'], 'approved')
        self.assertTrue(approved['approved_hash'])
        changed = self.room.save_draft(approved['id'], {
            'revision': approved['revision'], 'body': approved['body'] + '\nSửa nội dung.',
            'checks': approved['checks'],
        })
        self.assertEqual(changed['status'], 'draft')
        self.assertIsNone(changed['approved_hash'])
        self.assertFalse(any(changed['checks'].values()))
        with self.assertRaises(ValidationError):
            self.room.export(changed['id'])

    def test_page_or_source_edit_also_revokes(self):
        for field, value in [('page_name', 'Page khác'), ('sources', [])]:
            with self.subTest(field=field):
                draft = self.valid_draft()
                approved = self.room.approve(draft['id'], draft['revision'])
                if field == 'sources':
                    value = [dict(approved['sources'][0], summary='Bằng chứng được sửa')]
                updated = self.room.save_draft(approved['id'], {
                    'revision': approved['revision'], field: value,
                })
                self.assertEqual(updated['status'], 'draft')

    def test_revision_conflict_prevents_lost_update(self):
        draft = self.valid_draft()
        with self.assertRaises(Conflict):
            self.room.save_draft(draft['id'], {'revision': draft['revision'] - 1, 'title': 'stale'})

    def test_export_only_approved_then_manual_post_is_immutable(self):
        draft = self.valid_draft()
        with self.assertRaises(ValidationError):
            self.room.export(draft['id'])
        draft = self.room.approve(draft['id'], draft['revision'])
        exported = self.room.export(draft['id'])
        self.assertIn(draft['title'], exported)
        self.assertIn(self.item['url'], exported)
        with self.assertRaises(ValidationError):
            self.room.mark_published(draft['id'], draft['revision'], 'https://evil.example/post')
        posted = self.room.mark_published(draft['id'], draft['revision'],
                                          'https://www.facebook.com/example/posts/123')
        self.assertEqual(posted['status'], 'published')
        with self.assertRaises(Conflict):
            self.room.save_draft(posted['id'], {'revision': posted['revision'], 'body': 'overwrite'})
        self.assertTrue(self.room.history(posted['id']))

    def test_invalid_publication_url_does_not_change_draft_or_counts(self):
        draft = self.valid_draft()
        approved = self.room.approve(draft['id'], draft['revision'])
        before_history = self.room.history(approved['id'])
        before_stats = self.room.state()['stats']
        for url in ('', 'https://evil.example/post', 'https://facebook.com/',
                    'https://@facebook.com/example/posts/123', 'https://:@facebook.com/example/posts/123'):
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    self.room.mark_published(approved['id'], approved['revision'], url)
                self.assertEqual(self.room.draft(approved['id']), approved)
                self.assertEqual(self.room.history(approved['id']), before_history)
                self.assertEqual(self.room.state()['stats'], before_stats)

    def test_manual_article_rejects_empty_userinfo_without_saving(self):
        before = self.room.articles()
        for url in ('https://@example.com/news/other', 'https://:@example.com/news/other'):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                self.room.import_article({'title': 'Bài thử không hợp lệ', 'url': url, 'summary': 'Giả lập.'})
            self.assertEqual(self.room.articles(), before)

    def test_manual_source_is_not_automatically_fetched(self):
        result = self.room.import_article({
            'title': 'Nguồn do người dùng nhập', 'url': 'https://example.org/manual',
            'summary': 'Ghi chú do tôi tự đọc và ghi lại.',
        })
        self.assertTrue(result['id'])
        self.assertEqual(result['source_name'], 'Nhập thủ công')

    def test_manual_note_on_existing_url_is_labeled_as_manual(self):
        result = self.room.import_article({'title': self.item['title'], 'url': self.item['url'],
                                          'summary': 'User-written notes, not the publisher excerpt.'})
        self.assertEqual(result['source_name'], 'Nhập thủ công')
        self.assertEqual(result['sources'][0]['source_name'], 'Nhập thủ công')

    def test_manual_import_keeps_subscriptions_and_approved_draft_unchanged(self):
        draft = self.valid_draft()
        approved = self.room.approve(draft['id'], draft['revision'])
        before = self.room.export(approved['id'])
        subscriptions = self.room.collection_sources()
        with patch('newsroom.service.fetch_feed') as fetch:
            imported = self.room.import_article({
                'title': 'DEV Community', 'url': 'https://dev.to/',
                'summary': 'Ghi chú nhập thủ công, không phải nguồn theo dõi.',
            })
            fetch.assert_not_called()
        self.assertEqual(imported['source_name'], 'Nhập thủ công')
        self.assertEqual(self.room.collection_sources(), subscriptions)
        self.assertEqual(self.room.export(approved['id']), before)
        restarted = Newsroom(self.room.data_dir)
        self.assertEqual(restarted.article(imported['id'])['url'], 'https://dev.to/')
        self.assertEqual(restarted.export(approved['id']), before)

    def test_backup_integrity_and_restart(self):
        draft = self.valid_draft()
        backup = self.room.backup()
        with closing(sqlite3.connect(backup)) as conn:
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        restarted = Newsroom(Path(self.temp.name))
        self.assertEqual(restarted.draft(draft['id'])['body'], draft['body'])

    def test_same_headline_different_dates_is_not_merged(self):
        later = dict(self.item, url='https://example.com/another-week',
                     published_at='2026-10-01T08:00:00+00:00')
        self.assertEqual(self.room.ingest(self.source, [later])['added'], 1)

    def test_feed_correction_updates_candidate_not_saved_snapshot(self):
        draft = self.room.create_draft(self.article['id'])
        changed = dict(self.item, summary='Corrected summary from the publisher.')
        self.room.ingest(self.source, [changed])
        self.assertEqual(self.room.article(self.article['id'])['summary'], changed['summary'])
        self.assertEqual(self.room.draft(draft['id'])['sources'][0]['summary'], self.item['summary'])

    def test_unresolved_fact_marker_blocks_approval(self):
        draft = self.valid_draft()
        draft = self.room.save_draft(draft['id'], {'revision': draft['revision'],
                                                  'body': draft['body'] + ' [CẦN KIỂM TRA]'})
        draft = self.room.save_draft(draft['id'], {'revision': draft['revision'],
                                                  'checks': {key: True for key in self.room.CHECKS}})
        with self.assertRaises(ValidationError):
            self.room.approve(draft['id'], draft['revision'])

    def test_simultaneous_saves_only_one_wins(self):
        draft = self.valid_draft()
        def save(title):
            try:
                self.room.save_draft(draft['id'], {'revision': draft['revision'], 'title': title})
                return 'saved'
            except Conflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(save, ['First concurrent edit', 'Second concurrent edit'])),
                                  ['saved', 'conflict'])

    def test_metrics_only_manual_published_and_integer_values(self):
        draft = self.valid_draft()
        with self.assertRaises(ValidationError):
            self.room.save_metrics(draft['id'], {'saves': 3})
        draft = self.room.approve(draft['id'], draft['revision'])
        draft = self.room.mark_published(draft['id'], draft['revision'], 'https://facebook.com/page/posts/123')
        for invalid in [-1, 1.5, True, '3']:
            with self.assertRaises(ValidationError):
                self.room.save_metrics(draft['id'], {'saves': invalid})
        self.room.save_metrics(draft['id'], {'saves': 3, 'shares': 2, 'minutes': 50})
        self.assertEqual(self.room.state()['metrics'][draft['id']]['saves'], 3)

    def test_partial_feed_failure_is_visible_and_keeps_existing_articles(self):
        from newsroom.feeds import FeedError
        def response(source):
            if source['id'] == 'google':
                raise FeedError('Nguồn tạm lỗi.')
            return []
        with patch('newsroom.service.fetch_feed', side_effect=response):
            result = self.room.refresh()
        self.assertEqual(len(result['sources']), 4)
        self.assertFalse(result['sources'][0]['ok'])
        self.assertEqual(len(self.room.articles()), 1)
        self.room.refresh_lock.acquire()
        try:
            self.assertTrue(self.room.refresh()['busy'])
        finally:
            self.room.refresh_lock.release()

    def test_restore_never_overwrites_existing_directory(self):
        from newsroom.__main__ import restore
        draft = self.valid_draft()
        backup = self.room.backup()
        destination = Path(self.temp.name) / 'restored'
        restore(backup, destination)
        restored = Newsroom(destination)
        self.assertEqual(restored.draft(draft['id'])['body'], draft['body'])
        with self.assertRaises(ValueError):
            restore(backup, destination)


if __name__ == '__main__':
    unittest.main()
