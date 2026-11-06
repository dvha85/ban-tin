import unittest
from datetime import datetime, timedelta, timezone

from newsroom.feeds import canonical_url, parse_feed, rank_article, safe_url, FeedError


class FeedTests(unittest.TestCase):
    def test_canonical_url_removes_tracking_not_meaningful_query(self):
        self.assertEqual(
            canonical_url('https://EXAMPLE.com/story/?utm_source=x&id=2&fbclid=z#top'),
            'https://example.com/story?id=2',
        )

    def test_reject_unsafe_urls(self):
        for url in ['javascript:alert(1)', 'http://example.com', 'https://a:b@example.com/',
                    'https://127.0.0.1/', 'https://localhost/a', 'https://example.com:444/a',
                    'https://example.com/\nfoo', 'https://[::1]/']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                safe_url(url)

    def test_reject_empty_userinfo_without_rejecting_at_in_path_or_query(self):
        for url in ('https://@example.com/story', 'https://:@example.com/story',
                    'https://@example.com:443/story', 'https://:@example.com:443/story',
                    'https://user:@example.com/story', 'https://:password@example.com/story'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                safe_url(url)
        self.assertEqual(safe_url('https://example.com/a@b?email=x%40y'),
                         'https://example.com/a@b?email=x%40y')
        self.assertEqual(canonical_url('https://EXAMPLE.com:443/a@b?email=x%40y'),
                         'https://example.com/a@b?email=x%40y')

    def test_rss_strips_html_and_records_unknown_date(self):
        raw = b'''<rss><channel><item><title>New &amp; useful</title>
        <link>https://example.com/a?utm_campaign=x</link>
        <description>&lt;p&gt;Hello&lt;/p&gt;&lt;script&gt;bad()&lt;/script&gt;world</description>
        <pubDate>nonsense</pubDate></item></channel></rss>'''
        items = parse_feed(raw, 'https://example.com/feed')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], 'New & useful')
        self.assertNotIn('bad()', items[0]['summary'])
        self.assertIsNone(items[0]['published_at'])
        self.assertEqual(items[0]['url'], 'https://example.com/a')

    def test_atom_and_relative_links(self):
        raw = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Test</title>
        <link href="/news/one"/><updated>2026-10-14T00:00:00Z</updated>
        <summary>Short</summary></entry></feed>'''
        item = parse_feed(raw, 'https://example.com/feed')[0]
        self.assertEqual(item['url'], 'https://example.com/news/one')
        self.assertEqual(item['date_kind'], 'updated')

    def test_xml_entities_and_oversize_rejected(self):
        for raw in [b'<!DOCTYPE rss [<!ENTITY x "foo">]><rss/>', b'x' * 3_000_001,
                    '<!DOCTYPE rss [<!ENTITY x "foo">]><rss/>'.encode('utf-16')]:
            with self.assertRaises(FeedError):
                parse_feed(raw, 'https://example.com/feed')

    def test_invalid_item_does_not_break_feed(self):
        raw = b'''<rss><channel><item><title>Bad</title><link>javascript:bad</link></item>
        <item><title>Good</title><link>https://example.com/good</link></item></channel></rss>'''
        self.assertEqual(len(parse_feed(raw, 'https://example.com/feed')), 1)

    def test_scoring_is_editorial_not_search_volume(self):
        result = rank_article('AI assistant for everyday work', 'New app',
                              '2026-10-15T00:00:00+00:00',
                              datetime(2026, 10, 15, tzinfo=timezone.utc))
        self.assertEqual(result['category'], 'ai')
        self.assertTrue(result['reasons'])
        self.assertGreater(result['score'], 0)

    def test_future_dates_never_receive_recency_points(self):
        now = datetime(2026, 11, 6, 3, 0, tzinfo=timezone.utc)
        cases = (
            (now + timedelta(microseconds=1), 20, 'Ngày nguồn ở tương lai — cần kiểm tra'),
            (now + timedelta(minutes=30), 20, 'Ngày nguồn ở tương lai — cần kiểm tra'),
            (now + timedelta(hours=2, minutes=24), 20, 'Ngày nguồn ở tương lai — cần kiểm tra'),
            (now, 50, 'Nguồn có mốc thời gian trong 48 giờ'),
            (now - timedelta(days=2), 50, 'Nguồn có mốc thời gian trong 48 giờ'),
            (now - timedelta(days=2, microseconds=1), 35, 'Nguồn có mốc thời gian trong 7 ngày'),
            (now - timedelta(days=7), 35, 'Nguồn có mốc thời gian trong 7 ngày'),
        )
        for published_at, score, reason in cases:
            with self.subTest(published_at=published_at):
                result = rank_article('Thông báo giả', 'Nội dung giả', published_at.isoformat(), now)
                self.assertEqual(result['score'], score)
                self.assertIn(reason, result['reasons'])
        self.assertEqual(rank_article('Thông báo giả', '', None, now)['score'], 20)


if __name__ == '__main__':
    unittest.main()
