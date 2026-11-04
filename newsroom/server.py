"""Loopback-only personal application; never expose this server to the Internet."""
import hmac
import json
import math
import secrets
import sqlite3
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .service import Conflict, ValidationError

STATIC = Path(__file__).parent / 'static'
MAX_BODY = 128_000


def reject_json_constant(value):
    """Reject Python's non-standard NaN and Infinity JSON extensions."""
    raise ValueError('Invalid JSON constant')


def finite_json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('JSON number out of range')
    return number


def valid_path_id(value):
    """Accept bounded ASCII decimal identifiers before converting for SQLite."""
    return (bool(value) and len(value) <= 19 and value.isascii() and value.isdecimal()
            and int(value) <= 2**63 - 1)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, room, port):
        self.room = room
        self.session_key = secrets.token_urlsafe(32)
        self.csrf_token = secrets.token_urlsafe(32)
        self.job_lock = threading.Lock()
        super().__init__(('127.0.0.1', port), Handler)
        self.cookie_name = f'bantin_{self.server_address[1]}'
        self.origins = {f'http://127.0.0.1:{self.server_address[1]}',
                        f'http://localhost:{self.server_address[1]}'}
        self.hosts = {urlsplit(origin).netloc for origin in self.origins}

    def start_refresh(self):
        if not self.job_lock.acquire(blocking=False):
            return False

        def run():
            try:
                self.room.refresh()
            finally:
                self.job_lock.release()

        threading.Thread(target=run, daemon=True, name='source-refresh').start()
        return True

    def start_browser(self, job_id):
        if not self.job_lock.acquire(blocking=False):
            raise ValidationError('Đang có lượt thu thập chạy. Vui lòng chờ.')
        try:
            prepared = self.room.prepare_browser_job(job_id, confirmed=True)
        except Exception:
            self.job_lock.release()
            raise
        def run():
            try:
                self.room.run_prepared_browser_job(job_id, prepared)
            except ValidationError:
                pass  # Durable status is visible in the job list; no secrets in logs.
            finally:
                self.job_lock.release()
        threading.Thread(target=run, daemon=True, name='browser-collection').start()
        return True


class Handler(BaseHTTPRequestHandler):
    server_version = 'BanTinLocal'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        # No bodies, sources, tokens or authentication cookies in access logs.
        pass

    def respond(self, status, data, content_type='application/json; charset=utf-8', extra=None):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        elif isinstance(data, str):
            data = data.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Connection', 'close')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self'; object-src 'none'; "
                         "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def json_error(self, status, message, target=None):
        # Windows can reset a socket with unread request bytes, hiding the
        # intended 4xx response. Drain only a small declared body, with a short
        # timeout; never trust an unbounded Content-Length or chunked request.
        if self.command == 'POST' and not getattr(self, '_body_consumed', False):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not self.headers.get('Transfer-Encoding') and 0 < length <= 512_000:
                    self.connection.settimeout(1)
                    self.rfile.read(length)
            except (ValueError, OSError):
                pass
            finally:
                self._body_consumed = True
                self.connection.settimeout(15)
        result = {'error': message}
        if target is not None:
            result['target'] = target
        self.respond(status, result)

    def authorize(self, mutation=False):
        if self.headers.get('Host') not in self.server.hosts:
            self.json_error(403, 'Chỉ truy cập qua địa chỉ nội bộ của ứng dụng.')
            return False
        if not self.path.startswith('/api/'):
            return True
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            session = cookies.get(self.server.cookie_name)
            valid = session and hmac.compare_digest(session.value, self.server.session_key)
        except Exception:
            valid = False
        if not valid:
            self.json_error(401, 'Phiên đã hết hạn. Hãy tải lại trang Bàn tin.')
            return False
        if mutation and (self.headers.get('Origin') not in self.server.origins or not
                         hmac.compare_digest(self.headers.get('X-CSRF-Token', '').encode('utf-8'),
                                             self.server.csrf_token.encode('utf-8'))):
            self.json_error(403, 'Yêu cầu không thuộc phiên hiện tại. Hãy tải lại trang.')
            return False
        return True

    def do_GET(self):
        if not self.authorize():
            return
        path = urlsplit(self.path).path
        try:
            if path == '/':
                self.respond(200, (STATIC / 'index.html').read_bytes(), 'text/html; charset=utf-8', {
                    'Set-Cookie': f'{self.server.cookie_name}={self.server.session_key}; HttpOnly; SameSite=Strict; Path=/'})
            elif path in ('/static/app.js', '/static/draft-state.js', '/static/source-warnings.js', '/static/request-size.js', '/static/inbox-utils.js', '/static/app.css', '/static/favicon.svg'):
                filename = path.rsplit('/', 1)[1]
                content_type = {'js': 'text/javascript; charset=utf-8', 'css': 'text/css; charset=utf-8',
                                'svg': 'image/svg+xml'}[filename.rsplit('.', 1)[1]]
                self.respond(200, (STATIC / filename).read_bytes(), content_type)
            elif path == '/api/state':
                result = self.server.room.state()
                result['busy'] = result['busy'] or self.server.job_lock.locked()
                result['csrf_token'] = self.server.csrf_token
                self.respond(200, result)
            elif path == '/api/bulletins':
                self.respond(200, self.server.room.bulletins())
            elif path == '/api/bulletin-stats':
                self.respond(200, self.server.room.bulletin_stats())
            elif path == '/api/legacy-publication-duplicates':
                self.respond(200, self.server.room.legacy_publication_duplicates())
            elif path.startswith('/api/bulletins/'):
                parts = path.split('/')
                if len(parts) not in (4, 5) or not valid_path_id(parts[3]):
                    self.json_error(404, 'Không tìm thấy bản tin.')
                    return
                bulletin_id = int(parts[3])
                if len(parts) == 4:
                    self.respond(200, self.server.room.bulletin(bulletin_id))
                elif parts[4] == 'packet':
                    self.respond(200, {'text': self.server.room.bulletin_packet(bulletin_id)})
                elif parts[4] == 'variants':
                    self.respond(200, self.server.room.variants(bulletin_id))
                elif parts[4] == 'history':
                    self.respond(200, self.server.room.bulletin_history(bulletin_id))
                else:
                    self.json_error(404, 'Không tìm thấy chức năng.')
            elif path.startswith('/api/variants/'):
                parts = path.split('/')
                if len(parts) not in (4, 5) or not valid_path_id(parts[3]):
                    self.json_error(404, 'Không tìm thấy phiên bản.')
                    return
                variant_id = int(parts[3])
                if len(parts) == 4:
                    self.respond(200, self.server.room.variant(variant_id))
                elif parts[4] == 'export':
                    self.respond(200, self.server.room.export_variant(variant_id))
                elif parts[4] == 'archive':
                    self.respond(200, self.server.room.export_variant(variant_id, archive=True))
                elif parts[4] == 'download':
                    export = self.server.room.export_variant(variant_id)
                    self.respond(200, '\n\n---\n\n'.join(export['posts']), 'text/plain; charset=utf-8',
                                 {'Content-Disposition': f'attachment; filename="ban-tin-{variant_id}.txt"'})
                elif parts[4] == 'publications':
                    self.respond(200, self.server.room.publications(variant_id))
                else:
                    self.json_error(404, 'Không tìm thấy chức năng.')
            elif path.startswith('/api/drafts/'):
                parts = path.split('/')
                if len(parts) != 5 or not valid_path_id(parts[3]):
                    self.json_error(404, 'Không tìm thấy chức năng.')
                    return
                draft_id = int(parts[3])
                action = parts[4]
                if action == 'packet':
                    self.respond(200, {'text': self.server.room.packet(draft_id)})
                elif action == 'export':
                    self.respond(200, self.server.room.export(draft_id), 'text/plain; charset=utf-8',
                                 {'Content-Disposition': f'attachment; filename="bai-da-duyet-{draft_id}.txt"'})
                elif action == 'history':
                    self.respond(200, self.server.room.history(draft_id))
                else:
                    self.json_error(404, 'Không tìm thấy chức năng.')
            else:
                self.json_error(404, 'Không tìm thấy trang.')
        except ValidationError as exc:
            self.json_error(400, str(exc))
        except (sqlite3.Error, OSError):
            self.json_error(503, 'Chưa đọc được dữ liệu. Hãy thử lại; không xóa tệp dữ liệu.')

    def do_POST(self):
        if not self.authorize(mutation=True):
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json' or self.headers.get('Transfer-Encoding'):
            self.json_error(400, 'Cần dữ liệu JSON có kích thước xác định.')
            return
        try:
            size = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            size = -1
        if not 0 <= size <= MAX_BODY:
            self.json_error(413, 'Yêu cầu quá lớn hoặc thiếu kích thước.')
            return
        try:
            raw = self.rfile.read(size)
            self._body_consumed = True
            data = json.loads(raw, parse_constant=reject_json_constant, parse_float=finite_json_float)
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, UnicodeError, RecursionError, TimeoutError, OSError):
            self.json_error(400, 'Dữ liệu JSON không hợp lệ.')
            return
        path = urlsplit(self.path).path
        room = self.server.room
        try:
            if path == '/api/refresh':
                if room.demo:
                    raise ValidationError('Bản minh họa không tải tin thật. Hãy mở bản chính để lấy tin.')
                started = self.server.start_refresh()
                self.respond(202, {'started': started, 'busy': True})
            elif path == '/api/articles/import':
                self.respond(200, room.import_article(data))
            elif path == '/api/collection/sources':
                if not self.server.job_lock.acquire(blocking=False):
                    raise ValidationError('Đang có lượt thu thập chạy. Chờ hoàn tất rồi thêm nguồn.')
                try:
                    source = room.add_source(data)
                finally:
                    self.server.job_lock.release()
                self.respond(201, source)
            elif path.startswith('/api/collection/sources/'):
                source_id = path.rsplit('/', 1)[1]
                self.respond(200, room.configure_source(source_id, data))
            elif path.startswith('/api/collection/jobs/'):
                parts = path.split('/')
                if len(parts) != 6 or not valid_path_id(parts[4]):
                    raise ValidationError('Tác vụ không hợp lệ.')
                job_id, action = int(parts[4]), parts[5]
                if action == 'cancel':
                    self.respond(200, room.cancel_browser_job(job_id))
                elif action == 'run':
                    if room.demo or data.get('confirmed') is not True:
                        raise ValidationError('Cần xác nhận lượt AI; bản minh họa không chạy AI.')
                    self.server.start_browser(job_id)
                    self.respond(202, {'started': True})
                else:
                    self.json_error(404, 'Không tìm thấy chức năng.')
            elif path == '/api/drafts':
                article_id = data.get('article_id')
                if type(article_id) is not int:
                    raise ValidationError('Cần chọn một tin trước.')
                self.respond(200, room.create_draft(article_id))
            elif path == '/api/bulletins':
                self.respond(201, room.create_bulletin(data))
            elif path.startswith('/api/bulletins/'):
                parts = path.split('/')
                if len(parts) < 5 or not valid_path_id(parts[3]):
                    self.json_error(404, 'Không tìm thấy chức năng.')
                    return
                bulletin_id = int(parts[3])
                if len(parts) == 5 and parts[4] == 'save':
                    result = room.save_bulletin(bulletin_id, data)
                elif len(parts) == 5 and parts[4] == 'archive':
                    result = room.set_bulletin_archived(bulletin_id, data)
                elif len(parts) == 5 and parts[4] == 'items':
                    result = room.change_bulletin_items(bulletin_id, data)
                elif len(parts) == 5 and parts[4] == 'variants':
                    result = room.create_variant(bulletin_id, data)
                elif len(parts) == 7 and parts[4] == 'items' and valid_path_id(parts[5]) and parts[6] == 'save':
                    result = room.save_bulletin_item(bulletin_id, int(parts[5]), data)
                else:
                    self.json_error(404, 'Không tìm thấy chức năng.')
                    return
                self.respond(200, result)
            elif path.startswith('/api/variants/'):
                parts = path.split('/')
                if len(parts) != 5 or not valid_path_id(parts[3]):
                    self.json_error(404, 'Không tìm thấy chức năng.')
                    return
                variant_id, action = int(parts[3]), parts[4]
                if action == 'save':
                    result = room.save_variant(variant_id, data)
                elif action == 'preview':
                    result = room.preview_variant(variant_id, data)
                elif action == 'split':
                    result = room.split_variant(variant_id, data)
                elif action == 'approve':
                    result = room.approve_variant(variant_id, data)
                elif action == 'clone':
                    result = room.clone_variant(variant_id, data)
                elif action == 'publications':
                    result = room.record_publication(variant_id, data)
                else:
                    self.json_error(404, 'Không tìm thấy chức năng.')
                    return
                self.respond(200, result)
            elif path.startswith('/api/publications/'):
                parts = path.split('/')
                if len(parts) != 5 or not valid_path_id(parts[3]):
                    self.json_error(404, 'Không tìm thấy chức năng.')
                    return
                publication_id, action = int(parts[3]), parts[4]
                if action == 'corrections':
                    result = room.correct_publication(publication_id, data)
                elif action == 'metrics':
                    result = room.save_publication_metrics(publication_id, data)
                else:
                    self.json_error(404, 'Không tìm thấy chức năng.')
                    return
                self.respond(200, result)
            elif path == '/api/backup':
                self.respond(200, {'path': room.backup()})
            elif path.startswith('/api/drafts/'):
                parts = path.split('/')
                if len(parts) != 5 or not valid_path_id(parts[3]):
                    self.json_error(404, 'Không tìm thấy chức năng.')
                    return
                draft_id, action = int(parts[3]), parts[4]
                if action == 'save':
                    result = room.save_draft(draft_id, data)
                elif action == 'approve':
                    result = room.approve(draft_id, data.get('revision'))
                elif action == 'published':
                    result = room.mark_published(draft_id, data.get('revision'), data.get('post_url', ''))
                elif action == 'metrics':
                    result = room.save_metrics(draft_id, data)
                elif action == 'copy-bulletin':
                    result = room.copy_legacy_draft(draft_id, data)
                else:
                    self.json_error(404, 'Không tìm thấy chức năng.')
                    return
                self.respond(200, result)
            else:
                self.json_error(404, 'Không tìm thấy chức năng.')
        except Conflict as exc:
            self.json_error(409, str(exc), exc.target)
        except UnicodeError:
            self.json_error(400, 'Nội dung chứa ký tự Unicode không hợp lệ. Hãy nhập lại đoạn văn bản.')
        except (ValidationError, ValueError) as exc:
            self.json_error(400, str(exc))
        except (sqlite3.Error, OSError):
            self.json_error(503, 'Chưa lưu được dữ liệu. Giữ bản đang sửa và thử lại; không xóa tệp dữ liệu.')

    def do_OPTIONS(self):
        self.json_error(403, 'Không cho phép kết nối từ trang khác.')


def make_server(room, port=8877):
    return LocalServer(room, port)
