# Vendored text parser

`twitter_text/` is the pure Python MIT-licensed `twitter-text-parser` 3.0.0
distribution, from <https://github.com/swen128/twitter-text-python>. Its wheel
SHA-256 is `b36bd22e147db2234e79c73b021f10c3073e8c54f22b68c31696239b6917cdd3`.
The original license is included in `twitter_text/LICENSE`. The emoji data
file has its own Unicode copyright and terms-of-use notice in its header.

Local changes: package-relative imports in `__init__.py`, and reading the
bundled emoji data with `pathlib` instead of the undeclared `pkg_resources`
dependency. Upstream's bundled emoji list is Unicode 12.0 (2019), so unfamiliar
newer emoji sequences must not be represented as a guaranteed accurate count.
