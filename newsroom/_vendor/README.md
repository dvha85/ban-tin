# Vendored text parser

`twitter_text/` is the pure Python MIT-licensed `twitter-text-parser` 3.0.0
distribution, from <https://github.com/swen128/twitter-text-python>. Its wheel
SHA-256 is `b36bd22e147db2234e79c73b021f10c3073e8c54f22b68c31696239b6917cdd3`.
The original license is included in `twitter_text/LICENSE`. The emoji data
file has its own Unicode copyright and terms-of-use notice in its header.

Local changes: package-relative imports in `__init__.py`, reading the bundled
emoji data with `pathlib` instead of the undeclared `pkg_resources` dependency,
and an optional `emoji_extractor` parameter in `parse_tweet`. The default
extractor remains upstream's Unicode 12.0 list. The X counter injects the
separate Unicode 15.1 data in `newsroom/data`, while the Threads heuristic
continues using the default extractor. Neither establishes live X behavior.
