"""Bounded RSS/Atom discovery. Article URLs are never fetched automatically."""
import hashlib
import html
import ipaddress
import re
import socket
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

MAX_FEED_BYTES = 3_000_000
TRACKING = {'fbclid', 'gclid', 'msclkid', 'mc_cid', 'mc_eid'}


class FeedError(ValueError):
    pass


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'br', 'div', 'li'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value, limit=1200):
    parser = _PlainText()
    parser.feed(str(value or '')[:100_000])
    return re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()[:limit]


def safe_url(value):
    value = str(value).strip()
    if len(value) > 2000 or re.search(r'[\x00-\x20\x7f\\]', value):
        raise ValueError('Đường dẫn không hợp lệ.')
    try:
        parts = urllib.parse.urlsplit(value)
        host = parts.hostname
        if (parts.scheme != 'https' or not host or parts.username or parts.password
                or parts.port not in (None, 443) or '.' not in host
                or host.endswith(('.local', '.localhost', '.internal'))):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address and not address.is_global:
            raise ValueError()
        host.encode('idna')
    except (ValueError, UnicodeError):
        raise ValueError('Chỉ nhận liên kết HTTPS công khai, không chứa tài khoản hoặc cổng riêng.') from None
    return value


def canonical_url(value):
    parts = urllib.parse.urlsplit(safe_url(value))
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
    host = parts.hostname.lower().encode('idna').decode('ascii')
    path = parts.path.rstrip('/') or '/'
    return urllib.parse.urlunsplit(('https', host, path, urllib.parse.urlencode(sorted(query)), ''))


def title_key(value):
    normalized = unicodedata.normalize('NFKC', value).casefold()
    return hashlib.sha256(re.sub(r'[\W_]+', ' ', normalized).strip().encode()).hexdigest()


def parse_date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if parsed.tzinfo is None:
        # A missing timezone cannot establish a precise source publication time.
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def _tag(element):
    return element.tag.rsplit('}', 1)[-1].lower()


def parse_feed(raw, base_url):
    if len(raw) > MAX_FEED_BYTES:
        raise FeedError('RSS vượt giới hạn 3 MB.')
    # Also recognize UTF-16/32 DTD markers; ElementTree must never expand entities.
    probe = raw.replace(b'\x00', b'').upper()
    if b'<!DOCTYPE' in probe or b'<!ENTITY' in probe:
        raise FeedError('RSS có khai báo XML không an toàn.')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise FeedError('Nguồn không trả về RSS/Atom hợp lệ.') from None
    if _tag(root) not in ('rss', 'feed', 'rdf'):
        raise FeedError('Nguồn không phải RSS/Atom.')
    entries = [node for node in root.iter() if _tag(node) in ('item', 'entry')][:100]
    result = []
    for entry in entries:
        fields = {}
        link = ''
        for child in entry:
            tag = _tag(child)
            value = ''.join(child.itertext()).strip()
            fields.setdefault(tag, value)
            if tag == 'link' and child.attrib.get('rel', 'alternate') == 'alternate':
                link = child.attrib.get('href') or value
        title = plain_text(fields.get('title', ''), 300)
        if not title or not link:
            continue
        try:
            url = canonical_url(urllib.parse.urljoin(base_url, html.unescape(link)))
        except ValueError:
            continue
        date_kind = 'published'
        published_at = parse_date(fields.get('pubdate') or fields.get('published') or fields.get('date'))
        if not published_at:
            published_at = parse_date(fields.get('updated'))
            date_kind = 'updated' if published_at else 'unknown'
        summary = plain_text(fields.get('summary') or fields.get('description') or fields.get('encoded')
                             or fields.get('content') or '')
        result.append(dict(title=title, url=url, summary=summary,
                           published_at=published_at, date_kind=date_kind))
    return result


def rank_article(title, summary, published_at, now=None):
    """A transparent editorial heuristic, never an estimate of popularity."""
    now = now or datetime.now(timezone.utc)
    text = f'{title} {summary}'.lower()
    ai = bool(re.search(r'\b(ai|gemini|copilot|chatgpt|claude|llm|artificial intelligence)\b', text))
    practical = bool(re.search(r'\b(app|tool|feature|productivity|privacy|security|update|windows|iphone|android|laptop|how to)\b', text))
    reasons = []
    score = 20
    if ai:
        score += 25
        reasons.append('Có chủ đề AI')
    if practical:
        score += 20
        reasons.append('Có từ khóa sản phẩm / ứng dụng')
    if published_at:
        age = (now - datetime.fromisoformat(published_at)).total_seconds() / 86400
        if age < 0:
            reasons.append('Ngày nguồn ở tương lai — cần kiểm tra')
        elif age <= 2:
            score += 30
            reasons.append('Nguồn có mốc thời gian trong 48 giờ')
        elif age <= 7:
            score += 15
            reasons.append('Nguồn có mốc thời gian trong 7 ngày')
    else:
        reasons.append('Chưa rõ ngày đăng nguồn')
    return {'category': 'ai' if ai else 'tools', 'score': score,
            'reasons': reasons or ['Tin công nghệ từ nguồn đã chọn']}


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_fetch_url(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _validate_fetch_url(url, hosts):
    safe_url(url)
    host = urllib.parse.urlsplit(url).hostname
    if host not in hosts:
        raise FeedError('Nguồn chuyển tới tên miền ngoài danh sách cho phép.')
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise FeedError('Địa chỉ nguồn không công khai.')
    except socket.gaierror:
        raise FeedError('Không phân giải được tên miền nguồn.') from None


def fetch_feed(source):
    url = source['url']
    hosts = {urllib.parse.urlsplit(url).hostname}
    _validate_fetch_url(url, hosts)
    opener = urllib.request.build_opener(_SafeRedirect(hosts))
    req = urllib.request.Request(url, headers={
        'User-Agent': 'BanTinLocal/0.1 (personal RSS reader)',
        'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml',
        'Accept-Encoding': 'identity',
    })
    try:
        with opener.open(req, timeout=10) as response:
            raw = response.read(MAX_FEED_BYTES + 1)
        return parse_feed(raw, url)
    except urllib.error.HTTPError as exc:
        raise FeedError(f'Nguồn trả HTTP {exc.code}; không vượt chặn truy cập.') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise FeedError('Không tải được nguồn. Kiểm tra Internet hoặc thử lại sau.') from None
