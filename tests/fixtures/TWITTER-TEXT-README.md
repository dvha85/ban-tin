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

The separate `test_reference_javascript_310_characterization_for_newer_emoji`
cases were compared on 2026-11-03 with npm `twitter-text` 3.1.0 (tarball
integrity `sha512-nulfUi3FN6z0LUjYipJid+eiwXvOLb8Ass7Jy/6zsXmZK3URte043m8fL3FyDzrK+WLpyqhHuR/TcARTN/iuGQ==`)
and its resolved `twemoji-parser` 11.0.2. That package was installed only in a
temporary directory for comparison; it is not an application dependency. Both
implementations returned 9 for 🫱🏽‍🫲🏻 and 5 for ❤️‍🔥. The current X
documentation describes emoji sequences as weight 2, so these observations
do not establish how the live X client counts newer sequences. The test pins
the observed library behavior, not a claim of conformance to the live client.
