"""Pinned X twitter-text conformance cases; no network or YAML dependency."""
import json
import hashlib
import unittest
from pathlib import Path

from newsroom.social_formats import count_text
from newsroom._vendor.twitter_text import parse_tweet


class TwitterTextConformance(unittest.TestCase):
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
