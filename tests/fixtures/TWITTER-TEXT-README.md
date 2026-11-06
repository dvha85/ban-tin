# X text-count fixture

`twitter-text-conformance.json` is a reduced, mechanically transformed copy of
the `WeightedTweetsWithDiscountedEmojiCounterTest` and
`UnicodeDirectionalMarkerCounterTest` sections from
[twitter/twitter-text conformance/validate.yml](https://github.com/twitter/twitter-text/blob/30e2430d90cff3b46393ea54caf511441983c260/conformance/validate.yml),
commit `30e2430d90cff3b46393ea54caf511441983c260` (retrieved 2026-11-03).
The source file SHA-256 is
`29fa1be663676f3d0bb0a67f393b32c15d92c5dd10db9be401bf7708d7c5b703`.
Only description, text, weighted length and validity were retained; YAML was
converted to JSON so the application and its tests have no YAML dependency.
The upstream project is licensed under Apache License 2.0; see the adjacent
`TWITTER-TEXT-APACHE-2.0.txt`. These fixtures exercise the official published
examples, not every Unicode version or behavior of today's X application.

`twitter-text-weighted-legacy.json` contains the complete 20-case
`WeightedTweetsCounterTest` group from the same pinned `validate.yml`,
retrieved and hash-checked on 2026-11-06. The group predates the discounted
emoji configuration: 18 cases match the current counter, while the two named
emoji-sequence cases retain upstream expectations (16 and 9) but are checked
against current results (7 and 4). This difference is intentional, not a
claim about the behavior of the live X composer. Only description, text,
weighted length and validity were retained; YAML was converted to JSON.

`twitter-text-url-extract.json` contains the complete `urls`,
`urls_with_indices`, `urls_with_directional_markers` and
`tco_urls_with_params` sections (108 examples) from the same commit's
[conformance/extract.yml](https://github.com/twitter/twitter-text/blob/30e2430d90cff3b46393ea54caf511441983c260/conformance/extract.yml),
retrieved 2026-11-04. The source file SHA-256 is
`2b4f65d43462eb9785785eb94b633d1eccf920d5047fa17d98a45ea219851c71`.
The tests compare extracted URLs and, where provided, indices. For 76 ASCII URL
cases, another test derives the total using one per character and 23 per URL;
the other 15 non-ASCII cases are counted independently using NFC, upstream v3
character-weight ranges and the expected URL strings. These cases have no emoji
outside URLs. A separate test checks the emoji, NFC/NFD and URL examples in
[X counting documentation](https://docs.x.com/fundamentals/counting-characters)
as observed on 2026-11-05. This does not verify all weighted lengths or current X composer behavior. YAML was converted
to JSON for offline tests and requires no YAML package at runtime.

The separate `test_reference_javascript_310_characterization_for_newer_emoji`
cases were compared on 2026-11-03 with npm `twitter-text` 3.1.0 (tarball
integrity `sha512-nulfUi3FN6z0LUjYipJid+eiwXvOLb8Ass7Jy/6zsXmZK3URte043m8fL3FyDzrK+WLpyqhHuR/TcARTN/iuGQ==`)
and its resolved `twemoji-parser` 11.0.2. That package was installed only in a
temporary directory for comparison; it is not an application dependency. The
unmodified extractor in the Python vendored library also returned 9 for 🫱🏽‍🫲🏻
and 5 for ❤️‍🔥. The X counter now injects Unicode 15.1 emoji recognition and
returns 2 for each sequence, following X's documented general rule. The
characterization test still exercises the original extractor; neither test
establishes how the live X client counts these sequences.
