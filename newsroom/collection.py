"""Allowlisted, bounded collectors. No credentials, arbitrary URLs or model calls here."""
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

from .config import SOURCES
from .feeds import FeedError, canonical_url, parse_date, plain_text, safe_url

AGENT = 'BanTinLocal/0.3'
MAX_BYTES = 2_000_000
MAX_PAGES = 3
CATALOG = tuple(dict(s, kind='rss', default_enabled=True) for s in SOURCES) + (
    {'id': 'github-crawl4ai', 'name': 'Crawl4AI — GitHub Releases', 'kind': 'api',
     'url': 'https://api.github.com/repos/unclecode/crawl4ai/releases?per_page=10',
     'site': 'https://github.com/unclecode/crawl4ai/releases', 'color': '#315fc5',
     'article_host': 'github.com', 'prefix': '/unclecode/crawl4ai/releases/',
     'default_enabled': False},
    {'id': 'typesafe', 'name': 'TypeSafe AI — Blog', 'kind': 'web',
     'url': 'https://typesafe.ai/blog', 'site': 'https://typesafe.ai/blog',
     'prefix': '/blog/', 'color': '#326650', 'default_enabled': False},
    {'id': 'anthropic', 'name': 'Anthropic — News', 'kind': 'web',
     'url': 'https://www.anthropic.com/news', 'site': 'https://www.anthropic.com/news',
     'prefix': '/news/', 'color': '#aa6650', 'default_enabled': False},
)


class NeedsBrowser(FeedError):
    pass


class AccessBlocked(FeedError):
    pass


class PageNotFound(FeedError):
    pass


def source_by_id(source_id):
    for source in CATALOG:
        if source['id'] == source_id:
            return dict(source)
    raise FeedError('Nguồn không thuộc danh mục đã kiểm soát.')


def worker_source(payload):
    """Catalog entries are immutable; custom workers receive a validated snapshot, not DB access."""
    source_id = payload.get('source_id')
    if isinstance(source_id, str) and source_id.startswith('custom-'):
        from .subscriptions import custom_descriptor
        source = custom_descriptor(payload.get('source'))
        if source['id'] != source_id:
            raise FeedError('Mã nguồn không khớp cấu hình công cụ.')
        return source
    return source_by_id(source_id)


def public_ip(host):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise FeedError('Không phân giải được tên miền nguồn.') from None
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise AccessBlocked('Từ chối địa chỉ mạng không công khai.')
    return addresses[0][4][0]


def validate_target(url, source, resolve=True, resource=False):
    try:
        safe_url(url)
    except ValueError as exc:
        raise AccessBlocked(str(exc)) from None
    parts = urllib.parse.urlsplit(url)
    expected = urllib.parse.urlsplit(source['url'])
    # English slugs only in this curated catalog; reject encoded traversal/separators.
    if '%' in parts.path or any(s in ('.', '..') for s in parts.path.split('/')):
        raise AccessBlocked('Đường dẫn nguồn không an toàn.')
    if parts.hostname != expected.hostname:
        raise AccessBlocked('Tên miền ngoài nguồn được phép.')
    if not resource and source['kind'] == 'web':
        if parts.path.rstrip('/') != expected.path.rstrip('/') and not parts.path.startswith(source['prefix']):
            raise AccessBlocked('Trang ngoài chuyên mục đã chọn.')
    elif not resource and parts.path.rstrip('/') != expected.path.rstrip('/'):
        raise AccessBlocked('API ngoài điểm truy cập đã chọn.')
    if resolve:
        public_ip(parts.hostname)
    return url


def fetch_bytes(url, source, limit=MAX_BYTES, resource=False, return_url=False, robots_on_redirect=False):
    """Direct TLS to a prevalidated IP; no environment proxy, cookies or DNS rebinding."""
    for hop in range(4):
        validate_target(url, source, resource=resource)
        if hop and robots_on_redirect:
            check_robots(url, source)
        parts = urllib.parse.urlsplit(url)
        address = public_ip(parts.hostname)

        class PinnedTLS(http.client.HTTPSConnection):
            def connect(self):
                raw = socket.create_connection((address, 443), timeout=12)
                try:
                    self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=parts.hostname)
                except BaseException:
                    raw.close()
                    raise

        conn = PinnedTLS(parts.hostname, timeout=12)
        try:
            path = urllib.parse.urlunsplit(('', '', parts.path or '/', parts.query, ''))
            conn.request('GET', path, headers={'User-Agent': AGENT,
                         'Accept': 'application/rss+xml, application/atom+xml, application/xml, application/json, text/html, text/plain;q=0.9', 'Accept-Encoding': 'identity'})
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                url = urllib.parse.urljoin(url, response.getheader('Location', ''))
                continue
            if response.status == 404 and parts.path == '/robots.txt':
                return b'User-agent: *\nAllow: /\n'
            if response.status == 404:
                raise PageNotFound('Nguồn trả HTTP 404; không tìm thấy trang này.')
            if response.status != 200:
                raise AccessBlocked(f'Nguồn trả HTTP {response.status}; không vượt chặn truy cập.')
            if response.getheader('Content-Encoding', 'identity') not in ('', 'identity'):
                raise FeedError('Nguồn trả dữ liệu nén ngoài giao thức hỗ trợ.')
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise FeedError('Nội dung nguồn vượt giới hạn dung lượng.')
            return (raw, url) if return_url else raw
        except (OSError, http.client.HTTPException):
            raise FeedError('Không đọc được nguồn qua HTTPS. Không tự thay proxy hoặc vượt chặn.') from None
        finally:
            conn.close()
    raise AccessBlocked('Nguồn chuyển hướng quá nhiều lần.')


def check_robots(url, source):
    root = urllib.parse.urlunsplit(('https', urllib.parse.urlsplit(url).netloc, '/robots.txt', '', ''))
    raw = fetch_bytes(root, source, limit=256_000, resource=True)
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(raw.decode('utf-8', 'replace').splitlines())
    if not parser.can_fetch(AGENT, url):
        raise AccessBlocked('robots.txt không cho phép đọc trang này; chỉ nhập ghi chú thủ công.')
    delay = parser.crawl_delay(AGENT) or 0
    if delay > 10:
        raise AccessBlocked('Nguồn yêu cầu thời gian chờ dài; tạm dừng để kiểm tra thủ công.')
    return max(1, delay)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.links, self.parts, self.h1 = {}, [], [], []
        self.stack, self.hidden, self.anchor, self.label = [], 0, None, []
        self.article, self.main = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            self.meta[attrs.get('property') or attrs.get('name') or ''] = attrs.get('content', '')
        if tag == 'a':
            self.anchor, self.label = attrs.get('href'), []
        if tag not in ('meta', 'link', 'img', 'br', 'hr', 'input', 'source', 'wbr', 'area', 'base', 'embed', 'param'):
            self.stack.append(tag)
        if tag in ('script', 'style', 'nav', 'footer', 'header', 'noscript'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor:
            self.links.append((self.anchor, ' '.join(self.label)))
            self.anchor = None
        if tag in ('script', 'style', 'nav', 'footer', 'header', 'noscript'):
            self.hidden = max(0, self.hidden - 1)
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if self.anchor:
            self.label.append(data)
        if self.hidden:
            return
        self.parts.append(data)
        if 'article' in self.stack:
            self.article.append(data)
        if 'main' in self.stack:
            self.main.append(data)
        if 'h1' in self.stack:
            self.h1.append(data)


def discover_links(raw, source):
    page = Page()
    page.feed(raw[:MAX_BYTES])
    result = []
    for href, label in page.links:
        try:
            url = canonical_url(urllib.parse.urljoin(source['url'], href))
            validate_target(url, source, resolve=False)
            path = urllib.parse.urlsplit(url).path
            if path.rstrip('/') == urllib.parse.urlsplit(source['url']).path.rstrip('/') or len(label.strip()) < 8:
                continue
            if url not in result:
                result.append(url)
        except (ValueError, FeedError):
            continue
    return result[:30]


def extract_page(raw, url, source, method='crawl4ai'):
    if not isinstance(raw, str) or not raw or len(raw.encode('utf-8')) > MAX_BYTES:
        raise FeedError('Nội dung trang trống, sai định dạng hoặc vượt giới hạn.')
    validate_target(url, source, resolve=False)
    if canonical_url(url) == canonical_url(source['url']):
        raise FeedError('Trang chuyên mục không được ghi nhận thành bài viết.')
    page = Page()
    page.feed(raw[:MAX_BYTES])
    title = plain_text(page.meta.get('og:title') or ' '.join(page.h1), 300)
    content = re.sub(r'\s+', ' ', ' '.join(page.article or page.main or page.parts)).strip()
    if re.search(r'verify (?:that )?you are human|checking your browser|access denied|enable javascript and cookies|just a moment',
                 title + ' ' + content[:500], re.I):
        raise AccessBlocked('Trang yêu cầu xác minh/chặn truy cập; không dùng AI để vượt chặn.')
    if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', raw, re.I):
        raise AccessBlocked('Trang đánh dấu nội dung trả phí; không lấy bài tự động.')
    if len(title) < 5 or len(content) < 180:
        raise NeedsBrowser('Chưa đọc đủ nội dung; có thể cần điều hướng trình duyệt.')
    date = parse_date(page.meta.get('article:published_time', ''))
    date_kind = 'published' if date else 'unknown'
    if not date:
        date = parse_date(page.meta.get('article:modified_time', ''))
        date_kind = 'updated' if date else 'unknown'
    return dict(title=title, url=canonical_url(url), summary=content[:3000],
                published_at=date, date_kind=date_kind, collection_method=method,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                excerpt_hash=hashlib.sha256(content[:3000].encode()).hexdigest(), scope='excerpt')


def parse_api(raw, source):
    try:
        releases = json.loads(raw)
        if not isinstance(releases, list):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise FeedError('API không trả danh sách bản phát hành hợp lệ.') from None
    items = []
    for release in releases[:10]:
        if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
            continue
        try:
            url = canonical_url(release.get('html_url', ''))
            parts = urllib.parse.urlsplit(url)
            if parts.hostname != source['article_host'] or not parts.path.startswith(source['prefix']):
                continue
        except ValueError:
            continue
        title = plain_text(release.get('name') or release.get('tag_name'), 300)
        if len(title) < 4:
            continue
        body = plain_text(release.get('body', ''), 3000)
        date = parse_date(release.get('published_at', ''))
        items.append(dict(title=title, url=url, summary=body, published_at=date,
                          date_kind='published' if date else 'unknown', collection_method='api',
                          content_hash=hashlib.sha256(str(release.get('body', '')).encode()).hexdigest(),
                          excerpt_hash=hashlib.sha256(body.encode()).hexdigest(), scope='excerpt'))
    return items


def tools_python():
    override = os.environ.get('BANTIN_TOOLS_PYTHON')
    candidate = Path(override) if override else Path.home() / 'AppData/Local/BanTinTools/crawl-0.9.5/Scripts/python.exe'
    if not candidate.is_file():
        raise FeedError('Chưa có Crawl4AI cục bộ. Chạy CAI-CONG-CU-WEB.cmd; RSS/API vẫn dùng được.')
    return str(candidate)


def run_worker(mode, payload, timeout=120, python=None):
    if mode not in ('crawl', 'hermes'):
        raise FeedError('Loại công cụ không được phép.')
    root = Path(__file__).resolve().parent.parent
    # Workers get no app session, DB path or browser cookies. Process output is never shown raw.
    env = dict(os.environ, PYTHONIOENCODING='utf-8', ANONYMIZED_TELEMETRY='false', DO_NOT_TRACK='1')
    for key in list(env):
        if key.upper().endswith(('_API_KEY', '_TOKEN')) and key != 'BANTIN_BROWSER_API_KEY':
            env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix='bantin-worker-') as runtime, tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run([python or tools_python(), '-m', 'newsroom.collect_worker', mode],
                                    input=json.dumps(dict(payload, owner_pid=os.getpid(), runtime_dir=runtime)).encode(), stdout=output, stderr=subprocess.DEVNULL,
                                    cwd=root, env=env, timeout=timeout, shell=False,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired:
            raise FeedError('Tác vụ quá thời gian; đã dừng tiến trình. Không tự chạy lại tác vụ AI.') from None
        output.seek(0, 2)
        if output.tell() > 4_500_000:
            raise FeedError('Kết quả công cụ vượt giới hạn.')
        output.seek(0)
        lines = output.read().decode('utf-8', 'replace').splitlines()
    if result.returncode != 0:
        raise FeedError('Tiến trình công cụ chưa hoàn tất; không tự thử lại.')
    for line in reversed(lines):
        if line.startswith('BANTIN_RESULT:'):
            try:
                data = json.loads(line[len('BANTIN_RESULT:'):])
                if not isinstance(data, dict):
                    break
                if data.get('blocked') is True:
                    raise AccessBlocked('Nguồn bị chặn hoặc nằm ngoài phạm vi; không chuyển sang AI.')
                if data.get('ok') is not True:
                    raise FeedError('Công cụ chưa hoàn tất. Kiểm tra cài đặt hoặc đọc nguồn thủ công.')
                return data
            except (ValueError, AttributeError):
                break
    raise FeedError('Công cụ không trả kết quả hợp lệ; không tự chạy lại tác vụ AI.')


def collect_web(source, known=()):
    check_robots(source['url'], source)
    index = run_worker('crawl', {'source_id': source['id'], 'source': source, 'url': source['url']})
    validate_worker_page(index, source)
    # Index pages need the same block detection as articles, without requiring
    # article content or a publication date.
    check_page_access(index['html'])
    links = discover_links(index['html'], source)
    if not links:
        raise NeedsBrowser('Không thấy liên kết bài trong chuyên mục; cần kiểm tra trình duyệt.')
    items, warnings, needs_browser, errors = [], [], False, False
    for url in [u for u in links if u not in known][:MAX_PAGES]:
        try:
            delay = check_robots(url, source)
            rendered = run_worker('crawl', {'source_id': source['id'], 'source': source, 'url': url, 'delay': delay})
            validate_worker_page(rendered, source)
            items.append(extract_page(rendered['html'], rendered['url'], source))
        except AccessBlocked:
            raise
        except NeedsBrowser:
            needs_browser = True
            warnings.append('Một bài cần kiểm tra điều hướng; dữ liệu đã có được giữ nguyên.')
        except FeedError:
            errors = True
            warnings.append('Một bài chưa đọc được; dữ liệu đã có được giữ nguyên.')
    if warnings and not items:
        if needs_browser and not errors:
            raise NeedsBrowser('Có liên kết nhưng chưa đọc đủ bài; cần kiểm tra trình duyệt.')
        raise FeedError('Chưa đọc được bài; kiểm tra mạng/công cụ. Không tự chuyển lỗi sang AI.')
    return items, warnings


def check_page_access(raw):
    page = Page()
    page.feed(raw[:MAX_BYTES])
    visible = ' '.join(page.h1 + page.parts)[:2000]
    if re.search(r'verify (?:that )?you are human|checking your browser|access denied|enable javascript and cookies|just a moment', visible, re.I):
        raise AccessBlocked('Trang yêu cầu xác minh/chặn truy cập; không dùng AI để vượt chặn.')
    if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', raw, re.I):
        raise AccessBlocked('Trang đánh dấu nội dung trả phí; không lấy bài tự động.')


def validate_worker_page(page, source):
    if (not isinstance(page, dict) or not isinstance(page.get('url'), str)
            or not isinstance(page.get('html'), str) or not page['html']
            or len(page['html'].encode('utf-8')) > MAX_BYTES):
        raise FeedError('Công cụ không trả tư liệu trang hợp lệ trong giới hạn.')
    validate_target(page['url'], source, resolve=False)
