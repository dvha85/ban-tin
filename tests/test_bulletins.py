import tempfile
import unittest
from pathlib import Path

from newsroom.service import Conflict, Newsroom, ValidationError


class BulletinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.room = Newsroom(Path(self.temp.name))
        self.articles = []
        for index in range(3):
            self.articles.append(self.room.import_article({'title': f'Tin công nghệ thử nghiệm {index}',
                'url': f'https://example.com/story-{index}',
                'summary': f'Ghi chú kiểm chứng nguồn thử nghiệm thứ {index} đủ dài.'}))

    def tearDown(self):
        self.temp.cleanup()

    def create(self):
        return self.room.create_bulletin({'article_ids': [article['id'] for article in self.articles],
                                          'title': 'Bản tin thử nghiệm', 'edition_date': '2026-11-03'})

    def test_selection_validation_is_atomic(self):
        first = self.articles[0]['id']
        for ids in ([], [first, first], [first, 999999], [True], list(range(11))):
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                self.room.create_bulletin({'article_ids': ids})
        self.assertEqual(self.room.bulletins(), [])

    def test_reuse_counts_track_current_bulletins_without_preventing_reuse(self):
        first, second = (article['id'] for article in self.articles[:2])
        self.assertEqual(self.room.state()['bulletin_usage'], {})
        a = self.room.create_bulletin({'article_ids': [first]})
        b = self.room.create_bulletin({'article_ids': [first, second]})
        self.assertEqual(self.room.state()['bulletin_usage'], {first: 2, second: 1})
        self.room.change_bulletin_items(b['id'], {'revision': b['revision'],
                                                 'remove_item_id': b['items'][0]['id']})
        self.assertEqual(self.room.state()['bulletin_usage'], {first: 1, second: 1})
        self.assertEqual(self.room.bulletin(a['id'])['items'][0]['article_id'], first)

    def test_reorder_and_packet_preserve_snapshots_after_refresh_restart(self):
        bulletin = self.create()
        ids = [item['id'] for item in bulletin['items']]
        snapshot = bulletin['items'][0]['sources'][0]['summary']
        self.room.import_article({'title': self.articles[0]['title'], 'url': self.articles[0]['url'],
                                  'summary': 'Ghi chú nguồn mới không được thay bản đã chọn.'})
        bulletin = self.room.save_bulletin(bulletin['id'], {'revision': bulletin['revision'],
                                                            'item_ids': ids[::-1]})
        restarted = Newsroom(Path(self.temp.name))
        saved = restarted.bulletin(bulletin['id'])
        self.assertEqual([item['id'] for item in saved['items']], ids[::-1])
        self.assertEqual(saved['items'][-1]['sources'][0]['summary'], snapshot)
        packet = restarted.bulletin_packet(bulletin['id'])
        self.assertIn('DỮ LIỆU NGUỒN', packet)
        self.assertLess(packet.index('story-2'), packet.index('story-0'))

    def test_edits_reset_check_and_revision_conflict(self):
        bulletin = self.create()
        item = bulletin['items'][0]
        data = {'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
                'body': 'Một nội dung đã được biên tập.', 'verified': True}
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], data)
        self.assertFalse(bulletin['items'][0]['verified'])
        with self.assertRaises(Conflict):
            self.room.save_bulletin_item(bulletin['id'], item['id'], data)
        item = bulletin['items'][0]
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'], 'verified': True})
        self.assertTrue(bulletin['items'][0]['verified'])

    def test_add_remove_and_manual_source(self):
        bulletin = self.room.create_bulletin({'article_ids': [self.articles[0]['id']]})
        bulletin = self.room.change_bulletin_items(bulletin['id'], {'revision': bulletin['revision'],
                                                                    'article_id': self.articles[1]['id']})
        first, second = bulletin['items']
        bulletin = self.room.save_bulletin_item(bulletin['id'], first['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': first['revision'],
            'add_source': {'url': 'https://example.org/independent', 'title': 'Đối chiếu', 'summary': 'Ghi chú riêng'}})
        self.assertEqual(bulletin['items'][0]['sources'][1]['note_kind'], 'manual_note')
        bulletin = self.room.change_bulletin_items(bulletin['id'], {'revision': bulletin['revision'],
                                                                    'remove_item_id': second['id']})
        self.assertEqual(len(bulletin['items']), 1)
        self.assertEqual(len(bulletin['items'][0]['sources']), 2)
        item = bulletin['items'][0]
        remove_id = item['sources'][1]['source_id']
        bulletin = self.room.save_bulletin_item(bulletin['id'], item['id'], {
            'bulletin_revision': bulletin['revision'], 'revision': item['revision'], 'remove_source_id': remove_id})
        self.assertEqual(len(bulletin['items'][0]['sources']), 1)
        self.assertFalse(bulletin['items'][0]['verified'])
        self.assertEqual(self.room.bulletin_history(bulletin['id'])[0]['action'], 'saved')
        item = bulletin['items'][0]
        with self.assertRaises(ValidationError):
            self.room.save_bulletin_item(bulletin['id'], item['id'], {
                'bulletin_revision': bulletin['revision'], 'revision': item['revision'],
                'remove_source_id': item['sources'][0]['source_id']})
        with self.assertRaises(ValidationError):
            self.room.change_bulletin_items(bulletin['id'], {'revision': bulletin['revision'],
                                                            'remove_item_id': first['id']})

    def test_copy_legacy_is_unapproved_and_preserves_long_text_without_mutating_original(self):
        draft = self.room.create_draft(self.articles[0]['id'])
        draft = self.room.save_draft(draft['id'], {'revision': draft['revision'], 'title': 'Bài cũ',
            'body': 'a' * 5000, 'page_name': 'Trang thử'})
        with self.assertRaises(Conflict):
            self.room.copy_legacy_draft(draft['id'], {'revision': draft['revision'] - 1})
        copied = self.room.copy_legacy_draft(draft['id'], {'revision': draft['revision']})
        self.assertEqual(self.room.draft(draft['id']), draft)
        item = copied['bulletin']['items'][0]
        self.assertFalse(item['verified'])
        self.assertEqual(item['body'], '')
        self.assertIn('4.000', item['verification_note'])
        variant = self.room.variant(copied['variant_id'])
        self.assertEqual(variant['segments'][0]['text'], 'a' * 5000)
        self.assertEqual(variant['status'], 'draft')
        self.assertFalse(any(variant['checks'].values()))
        with self.assertRaises(ValidationError):
            self.room.export_variant(variant['id'])

    def test_copy_legacy_requires_explicit_source_choice_when_more_than_three(self):
        draft = self.room.create_draft(self.articles[0]['id'])
        sources = draft['sources'] + [{'url': f'https://other.example/source-{i}', 'title': '',
            'summary': '', 'source_name': 'Nguồn thử', 'retrieved_at': '', 'date_kind': 'unknown'} for i in range(3)]
        draft = self.room.save_draft(draft['id'], {'revision': draft['revision'], 'sources': sources})
        with self.assertRaises(ValidationError):
            self.room.copy_legacy_draft(draft['id'], {'revision': draft['revision']})
        with self.assertRaises(ValidationError):
            self.room.copy_legacy_draft(draft['id'], {'revision': draft['revision'],
                                                       'source_selection': ['https://not-in-draft.example/']})
        self.assertEqual(self.room.bulletins(), [])
        chosen = [source['url'] for source in sources[-2:]]
        result = self.room.copy_legacy_draft(draft['id'], {'revision': draft['revision'], 'source_selection': chosen})
        self.assertEqual([source['url'] for source in result['bulletin']['items'][0]['sources']], chosen)


if __name__ == '__main__':
    unittest.main()
