"""Pinned X twitter-text conformance cases; no network or YAML dependency."""
import json
import hashlib
import unittest
import unicodedata
from pathlib import Path

from newsroom.social_formats import count_text
from newsroom._vendor.twitter_text import extract_urls, extract_urls_with_indices, parse_tweet


class TwitterTextConformance(unittest.TestCase):
    def test_url_extraction_matches_upstream_corpus(self):
        path = Path(__file__).parent / 'fixtures' / 'twitter-text-url-extract.json'
        fixture = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(fixture['source_commit'], '30e2430d90cff3b46393ea54caf511441983c260')
        self.assertEqual(fixture['source_sha256'], '2b4f65d43462eb9785785eb94b633d1eccf920d5047fa17d98a45ea219851c71')
        expected_sizes = {'urls': 91, 'urls_with_indices': 10,
                          'urls_with_directional_markers': 2, 'tco_urls_with_params': 5}
        self.assertEqual({group: len(cases) for group, cases in fixture['groups'].items()}, expected_sizes)
        for group, cases in fixture['groups'].items():
            for case in cases:
                with self.subTest(group=group, description=case['description']):
                    extractor = extract_urls_with_indices if group in (
                        'urls_with_indices', 'urls_with_directional_markers') else extract_urls
                    self.assertEqual(extractor(case['text']), case['expected'])

    def test_x_count_uses_upstream_ascii_url_boundaries(self):
        path = Path(__file__).parent / 'fixtures' / 'twitter-text-url-extract.json'
        fixture = json.loads(path.read_text(encoding='utf-8'))
        cases = [case for case in fixture['groups']['urls'] if case['text'].isascii()]
        self.assertEqual(len(cases), 76)
        for case in cases:
            with self.subTest(description=case['description']):
                # ASCII weighs one per character; replace each expected URL's
                # weight with 23 according to the pinned X counting policy.
                expected = len(case['text']) + sum(23 - len(url) for url in case['expected'])
                self.assertEqual(count_text('x', case['text'])[0], expected)

    def test_x_count_uses_upstream_non_ascii_url_boundaries(self):
        path = Path(__file__).parent / 'fixtures' / 'twitter-text-url-extract.json'
        fixture = json.loads(path.read_text(encoding='utf-8'))
        cases = [case for case in fixture['groups']['urls'] if not case['text'].isascii()]
        self.assertEqual(len(cases), 15)
        # Pinned twitter-text v3 weights: ranges with weight 1; all other code
        # points have weight 2. The corpus cases have no emoji outside URLs.
        ranges = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
        def weight(text):
            return sum(1 if any(start <= ord(ch) <= end for start, end in ranges) else 2 for ch in text)
        for case in cases:
            with self.subTest(description=case['description']):
                text = unicodedata.normalize('NFC', case['text'])
                start = total = 0
                for url in case['expected']:
                    url = unicodedata.normalize('NFC', url)
                    position = text.find(url, start)
                    self.assertGreaterEqual(position, start)
                    total += weight(text[start:position]) + 23
                    start = position + len(url)
                total += weight(text[start:])
                self.assertEqual(count_text('x', case['text'])[0], total)

    def test_x_documented_emoji_normalization_and_url_examples(self):
        # https://docs.x.com/fundamentals/counting-characters (2026-11-05)
        examples = [('👾', 2), ('🙋🏽', 2), ('👨‍🎤', 2), ('👨‍👩‍👧‍👦', 2),
                    ('café', 4), ('cafe\u0301', 4), ('https://example.com', 23),
                    ('https://example.com/very/long/path', 23)]
        for text, expected in examples:
            with self.subTest(text=text):
                self.assertEqual(count_text('x', text), (expected, True))

    def test_x_counts_crlf_without_silently_collapsing_two_characters(self):
        # Pinned upstream JS parseTweet normalizes NFC but does not collapse CRLF.
        for text, length in (('A\r\nB', 4), ('A\nB', 3), ('A\rB', 3),
                             ('cafe\u0301\r\nB', 7)):
            with self.subTest(text=repr(text)):
                self.assertEqual(count_text('x', text), (length, True))
        self.assertEqual(count_text('x', 'a' * 277 + '\r\nX'), (280, True))
        self.assertEqual(count_text('x', 'a' * 278 + '\r\nX'), (281, False))

    def test_weighted_lengths_and_validity_from_upstream(self):
        path = Path(__file__).parent / 'fixtures' / 'twitter-text-conformance.json'
        fixture = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(fixture['source_commit'], '30e2430d90cff3b46393ea54caf511441983c260')
        self.assertEqual(len(fixture['cases']), 24)
        for case in fixture['cases']:
            with self.subTest(group=case['group'], description=case['description']):
                self.assertEqual(count_text('x', case['text']), (case['weightedLength'], case['valid']))

    def test_reference_javascript_310_characterization_for_newer_emoji(self):
        # Values captured from twitter-text 3.1.0 with twemoji-parser 11.0.2;
        # this characterizes that implementation, not live X behavior.
        cases = [('🫱🏽‍🫲🏻', 9), ('🧑‍🦯‍➡️', 8), ('❤️‍🔥', 5),
                 ('🏳️‍⚧️', 7), ('👨‍👩‍👧‍👦', 2),
                 ('https://example.photography/a', 23), ('https://example.zip/a', 23)]
        for text, expected in cases:
            with self.subTest(text=text):
                result = parse_tweet(text)
                self.assertEqual((result.weightedLength, result.valid), (expected, True))

    def test_x_counts_unicode_151_emoji_sequences_as_one_weighted_emoji(self):
        for text in ('🫱🏽‍🫲🏻', '🧑‍🦯‍➡️', '❤️‍🔥', '🏳️‍⚧️', '👨‍👩‍👧‍👦'):
            with self.subTest(text=text):
                self.assertEqual(count_text('x', text), (2, True))
        self.assertEqual(count_text('x', '❤️‍🔥' * 140), (280, True))
        self.assertEqual(count_text('x', '❤️‍🔥' * 141), (282, False))
        self.assertEqual(count_text('x', '12 # test'), (9, True))

    def test_unicode_emoji_source_is_pinned(self):
        path = Path(__file__).parents[1] / 'newsroom' / 'data' / 'emoji-test-15.1.txt'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         'd876ee249aa28eaa76cfa6dfaa702847a8d13b062aa488d465d0395ee8137ed9')


if __name__ == '__main__':
    unittest.main()
