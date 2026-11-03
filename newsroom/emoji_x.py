"""Versioned emoji recognition for X's weighted text counter."""
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _emoji_pattern():
    source = Path(__file__).with_name('data') / 'emoji-test-15.1.txt'
    sequences = set()
    for line in source.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#') or ';' not in line:
            continue
        codepoints, remainder = line.split(';', 1)
        status = remainder.split('#', 1)[0].strip()
        if status not in {'fully-qualified', 'minimally-qualified', 'unqualified'}:
            continue
        sequences.add(''.join(chr(int(point, 16)) for point in codepoints.split()))
    if not sequences:
        raise RuntimeError('Thiếu dữ liệu emoji cho bộ đếm X.')
    # Longest sequences must win over their individual emoji prefixes.
    return re.compile('|'.join(re.escape(s) for s in sorted(sequences, key=lambda s: (-len(s), s))))


def extract_x_emojis(text):
    return [{'emoji': match.group(), 'indices': [match.start(), match.end()]}
            for match in _emoji_pattern().finditer(text)]
