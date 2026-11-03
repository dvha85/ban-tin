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
