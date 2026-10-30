"""User-confirmed subscriptions, with bounded same-host RSS discovery and no AI."""
import re
import urllib.parse
from html.parser import HTMLParser

from .collection import (AccessBlocked, check_page_access, check_robots, fetch_bytes,
                         validate_target)
from .feeds import FeedError, MAX_FEED_BYTES, canonical_url, parse_feed, safe_url

MAX_CUSTOM_SOURCES = 20


def subscription_url(value):
    if not isinstance(value, str):
        raise FeedError('Địa chỉ nguồn phải là liên kết HTTPS công khai.')
    try:
        url = safe_url(value)
        parts = urllib.parse.urlsplit(url)
        # Keep a trailing slash for relative HTML links; canonical_url is only a key.
        normalized = urllib.parse.urlsplit(canonical_url(url))
        path = normalized.path + ('/' if parts.path.endswith('/') and normalized.path != '/' else '')
        if not path.isascii() or '%' in path or any(p in ('.', '..') for p in path.split('/')):
            raise ValueError('Đường dẫn có mã hóa hoặc chuyển thư mục không được hỗ trợ.')
        sensitive = {'key', 'api_key', 'apikey', 'token', 'access_token', 'auth', 'authorization',
                     'password', 'secret', 'signature'}
        if any(k.casefold() in sensitive for k, _ in urllib.parse.parse_qsl(parts.query)):
            raise ValueError('Không dùng nguồn có khóa bí mật hoặc thông tin đăng nhập trong URL.')
        return urllib.parse.urlunsplit(('https', normalized.netloc, path, normalized.query, ''))
    except ValueError as exc:
        raise FeedError(str(exc)) from None


def validate_prefix(prefix):
    if (not isinstance(prefix, str) or not prefix.startswith('/') or not prefix.endswith('/')
            or len(prefix) > 500 or re.search(r'[\s%?#\\]', prefix)
            or any(p in ('.', '..') for p in prefix.split('/')) or '//' in prefix):
        raise FeedError('Phạm vi web phải bắt đầu và kết thúc bằng /, ví dụ /news/; dùng / cho cả tên miền.')
    return prefix


def custom_descriptor(data):
    """Revalidate a persisted/worker snapshot; never accept an arbitrary API adapter."""
    if not isinstance(data, dict):
        raise FeedError('Cấu hình nguồn theo dõi không hợp lệ.')
    source_id, name, kind = data.get('id'), data.get('name'), data.get('kind')
    if (not isinstance(source_id, str) or not re.fullmatch(r'custom-[0-9a-f]{32}', source_id)
            or not isinstance(name, str) or not 2 <= len(name.strip()) <= 120
            or any(ord(c) < 32 for c in name) or kind not in ('rss', 'web')):
        raise FeedError('Cấu hình nguồn theo dõi không hợp lệ.')
    url = subscription_url(data.get('url'))
    site = subscription_url(data.get('site'))
    if urllib.parse.urlsplit(site).hostname != urllib.parse.urlsplit(url).hostname:
        raise FeedError('Trang nguồn và địa chỉ đọc phải cùng tên miền.')
    prefix = validate_prefix(data.get('prefix')) if kind == 'web' else ''
    source = dict(id=source_id, name=name.strip(), kind=kind, url=url, site=site,
                  prefix=prefix, custom=True, default_enabled=False, color='#326650')
    validate_target(url, source, resolve=False)
    return source


def read_public(url):
    """All discovery/refresh requests use robots checks and IP-pinned HTTPS."""
    url = subscription_url(url)
    scope = {'kind': 'rss', 'url': url}
    check_robots(url, scope)
    return fetch_bytes(url, scope, limit=MAX_FEED_BYTES, return_url=True, robots_on_redirect=True)


class FeedLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if (tag == 'link' and 'alternate' in (attrs.get('rel') or '').lower().split()
                and (attrs.get('type') or '').lower().split(';')[0] in
                ('application/rss+xml', 'application/atom+xml') and attrs.get('href')):
            self.links.append(attrs['href'])


def discover_source(url, kind, prefix):
    url = subscription_url(url)
    if kind not in ('auto', 'rss', 'web'):
        raise FeedError('Chọn tìm RSS/Atom hoặc đọc web; API riêng cần adapter được kiểm tra.')
    if kind == 'web':
        prefix = validate_prefix(prefix)
    raw, final = read_public(url)
    # read_public already checks redirects; validate again for independent mocks/protocols.
    final = subscription_url(final)
    validate_target(final, {'url': url, 'kind': 'rss'}, resolve=False)
    if kind == 'web':
        check_page_access(raw.decode('utf-8', 'replace'))
        return dict(kind='web', url=final, site=final, prefix=prefix)
    try:
        parse_feed(raw, final)
        root = urllib.parse.urlunsplit(('https', urllib.parse.urlsplit(final).netloc, '/', '', ''))
        return dict(kind='rss', url=final, site=root, prefix='')
    except FeedError:
        if kind == 'rss':
            raise
    text = raw.decode('utf-8', 'replace')
    if not re.search(r'<(?:html|head|link|body)\b', text, re.I):
        raise FeedError('Nguồn không trả RSS/Atom hoặc trang web hợp lệ.')
    check_page_access(text)
    parser = FeedLinks()
    parser.feed(text)
    candidates = []
    for href in parser.links + ['/feed', '/rss.xml', '/feed.xml']:
        try:
            candidate = subscription_url(urllib.parse.urljoin(final, href))
            if urllib.parse.urlsplit(candidate).hostname != urllib.parse.urlsplit(final).hostname:
                continue
            if canonical_url(candidate) != canonical_url(final) and candidate not in candidates:
                candidates.append(candidate)
        except FeedError:
            continue
    for candidate in candidates[:3]:
        try:
            feed, endpoint = read_public(candidate)
            endpoint = subscription_url(endpoint)
            validate_target(endpoint, {'url': candidate, 'kind': 'rss'}, resolve=False)
            parse_feed(feed, endpoint)
            return dict(kind='rss', url=endpoint, site=final, prefix='')
        except AccessBlocked:
            # Never turn access denial into another crawl/AI attempt.
            raise
        except FeedError:
            continue
    raise FeedError('Chưa tìm thấy RSS/Atom cùng tên miền. Hãy dán URL RSS chính xác, '
                    'hoặc chọn “Đọc web” và nhập phạm vi chuyên mục. Chưa thêm nguồn, chưa gọi AI.')


def collect_subscription(source):
    raw, final = read_public(source['url'])
    validate_target(final, source, resolve=False)
    return parse_feed(raw, final)
