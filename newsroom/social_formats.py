"""Deterministic rendering of the exact text a person can copy or export."""
import re
import unicodedata

from ._vendor.twitter_text import parse_tweet, extract_emojis_with_indices
from .emoji_x import extract_x_emojis

POLICY_VERSION = '2026-11-04-v5'
RENDERER_VERSION = '1'
LIMITS = {'facebook': 12000, 'threads': 500, 'x': 280}
MAX_SEGMENTS = 20


def thread_length(text):
    # Heuristic only: the vendored emoji list predates newer emoji. This does
    # not establish an upper bound or reproduce Meta's undocumented counting.
    count = len(text)
    for match in extract_emojis_with_indices(text):
        emoji = match['emoji']
        count += len(emoji.encode('utf-8')) - len(emoji)
    return count


def count_text(platform, text):
    if platform == 'x':
        parsed = parse_tweet(text, emoji_extractor=extract_x_emojis)
        return parsed.weightedLength, parsed.valid
    if platform == 'threads':
        value = thread_length(text)
        return value, value <= LIMITS['threads']
    if platform == 'facebook':
        value = len(text)
        return value, value <= LIMITS['facebook']
    raise ValueError('Nền tảng không được hỗ trợ.')


def render_segments(platform, segments, bulletin):
    from .service import ValidationError
    if platform not in LIMITS or not isinstance(segments, list) or not 1 <= len(segments) <= MAX_SEGMENTS:
        raise ValidationError('Cần chọn nền tảng và từ 1 đến 20 đoạn.')
    if platform == 'facebook' and len(segments) != 1:
        raise ValidationError('Bản Facebook chỉ gồm một bài.')
    items = {item['id']: item for item in bulletin['items']}
    posts = []
    for position, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValidationError('Đoạn bài không hợp lệ.')
        text = segment.get('text', '')
        item_ids = segment.get('item_ids', [])
        if not isinstance(text, str) or len(text) > 12000 or '\x00' in text:
            raise ValidationError('Nội dung đoạn không hợp lệ hoặc vượt 12.000 ký tự.')
        if (not isinstance(item_ids, list) or not item_ids or any(type(i) is not int for i in item_ids)
                or len(set(item_ids)) != len(item_ids) or any(i not in items for i in item_ids)):
            raise ValidationError('Mỗi đoạn phải chọn các mục tin thuộc bản tin này.')
        available = {source['source_id']: source for item_id in item_ids for source in items[item_id]['sources']}
        source_ids = segment.get('source_ids')
        if source_ids is None:
            source_ids = list(available)
        if (not isinstance(source_ids, list) or any(not isinstance(s, str) for s in source_ids)
                or len(set(source_ids)) != len(source_ids) or any(s not in available for s in source_ids)):
            raise ValidationError('Nguồn trong đoạn không thuộc các mục đã chọn.')
        for item_id in item_ids:
            if not any(source['source_id'] in source_ids for source in items[item_id]['sources']):
                raise ValidationError('Mỗi mục xuất hiện trong đoạn cần ít nhất một nguồn.')
        urls = list(dict.fromkeys(available[source_id]['url'] for source_id in source_ids))
        prefix = f'{position + 1}/{len(segments)} ' if len(segments) > 1 else ''
        rendered = prefix + text.strip() + ('\n\nNguồn: ' + ' '.join(urls) if urls else '')
        length, within_limit = count_text(platform, rendered)
        posts.append({'position': position, 'text': rendered, 'body': text.strip(), 'item_ids': item_ids,
                      'source_ids': source_ids, 'urls': urls, 'length': length,
                      'limit': LIMITS[platform], 'valid': bool(text.strip()) and within_limit})
    return {'platform': platform, 'policy_version': POLICY_VERSION, 'renderer_version': RENDERER_VERSION,
            'posts': posts, 'valid': all(post['valid'] for post in posts),
            'warning': ('Bộ đếm Threads chỉ là ước lượng, có thể đếm thiếu; kiểm tra lại trên nền tảng.'
                        if platform == 'threads' else
                        'Bộ đếm X là công cụ hỗ trợ; kiểm tra lại trên nền tảng, đặc biệt với emoji mới.'
                        if platform == 'x' else 'Giới hạn 12.000 ký tự là giới hạn nội bộ.')}


def split_segments(platform, segments, bulletin):
    """Split only at paragraph or sentence boundaries, preserving attribution.

    Retry with the actual total until numbering and length calculations agree.
    Never split a token or silently shorten text, including an oversized sentence.
    """
    from .service import ValidationError
    rendered = render_segments(platform, segments, bulletin)
    if platform == 'facebook':
        if not rendered['valid']:
            raise ValidationError('Bài Facebook quá dài hoặc còn trống; hãy tự biên tập ngắn lại.')
        return segments
    if any(not post['body'] for post in rendered['posts']):
        raise ValidationError('Hãy nhập nội dung cho từng đoạn trước khi chia.')
    units = []
    for segment, post in zip(segments, rendered['posts']):
        # A boundary consists solely of whitespace after punctuation or a
        # paragraph break; no URL, word, or joined character is cut apart.
        sentences = re.split(r'(?<=[.!?。！？])(?=\s)|(?<=\n)(?=\n)', segment['text'].strip())
        parts = []
        whitespace = ''
        for part in sentences:
            if not part.strip():
                whitespace += part
            else:
                parts.append(whitespace + part)
                whitespace = ''
        if whitespace and parts:
            parts[-1] += whitespace
        units.append((parts, segment, post['urls']))
    assumed_total = len(segments)
    for _ in range(MAX_SEGMENTS + 1):
        result = []
        for parts, segment, urls in units:
            current = ''
            suffix = '\n\nNguồn: ' + ' '.join(urls)
            for part in parts:
                proposed = current + part
                position = len(result) + 1
                prefix = f'{position}/{assumed_total} ' if assumed_total > 1 else ''
                _, valid = count_text(platform, prefix + proposed.strip() + suffix)
                if valid:
                    current = proposed
                    continue
                if not current.strip():
                    raise ValidationError('Có câu hoặc đoạn quá dài để chia an toàn cùng nguồn; hãy tự viết ngắn lại.')
                result.append({**segment, 'text': current.strip()})
                if len(result) >= MAX_SEGMENTS:
                    raise ValidationError('Cần quá 20 đoạn; hãy tự biên tập ngắn lại.')
                current = part
                prefix = f'{len(result) + 1}/{assumed_total} ' if assumed_total > 1 else ''
                if not count_text(platform, prefix + current.strip() + suffix)[1]:
                    raise ValidationError('Có câu hoặc đoạn quá dài để chia an toàn cùng nguồn; hãy tự viết ngắn lại.')
            if current.strip():
                result.append({**segment, 'text': current.strip()})
        if len(result) > MAX_SEGMENTS:
            raise ValidationError('Cần quá 20 đoạn; hãy tự biên tập ngắn lại.')
        if len(result) == assumed_total:
            if not render_segments(platform, result, bulletin)['valid']:
                raise ValidationError('Không thể chia an toàn; hãy tự biên tập ngắn lại.')
            return result
        assumed_total = len(result)
    raise ValidationError('Không thể ổn định đánh số đoạn; hãy tự chia thủ công.')
