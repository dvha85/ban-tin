"""Durable collection settings/jobs, deliberately separate from editorial approval."""
import json
import os
import shutil
import secrets
from datetime import datetime, timezone
from pathlib import Path

from .collection import (CATALOG, MAX_PAGES, NeedsBrowser, collect_web, extract_page,
                         fetch_bytes, parse_api, run_worker, tools_python, validate_worker_page)
from .feeds import FeedError
from .feeds import canonical_url
from .subscriptions import (MAX_CUSTOM_SOURCES, custom_descriptor,
                            discover_source, subscription_url, validate_prefix)


def at():
    return datetime.now(timezone.utc).isoformat()


class CollectionMixin:
    def init_collection(self):
        with self.connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS collection_settings (
                    source_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL,
                    confirmed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collection_jobs (
                    id INTEGER PRIMARY KEY, source_id TEXT NOT NULL,
                    status TEXT NOT NULL, reason TEXT NOT NULL, message TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS active_collection_job
                    ON collection_jobs(source_id) WHERE status IN ('pending','running','unknown');
                CREATE TABLE IF NOT EXISTS collection_evidence (
                    url TEXT PRIMARY KEY, collection_method TEXT NOT NULL,
                    content_hash TEXT NOT NULL, excerpt_hash TEXT NOT NULL, scope TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collection_attempts (
                    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES collection_jobs(id),
                    started_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS custom_sources (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
                    url TEXT NOT NULL, url_key TEXT NOT NULL UNIQUE, input_url TEXT NOT NULL,
                    site TEXT NOT NULL, prefix TEXT NOT NULL, created_at TEXT NOT NULL
                );
                PRAGMA user_version=3;
            ''')
        self.recover_collection_jobs()

    def recover_collection_jobs(self):
        # Run timeout is <=180s. Do not re-dispatch a possibly paid abandoned call.
        with self.connection() as conn:
            conn.execute("""UPDATE collection_jobs SET status='unknown',message=?
                WHERE status='running' AND julianday(updated_at)<julianday('now','-10 minutes')""",
                ('Lượt chạy mất dấu sau gián đoạn. Kiểm tra trước khi hủy; không tự chạy lại.',))

    def collection_sources(self):
        with self.connection() as conn:
            settings = {r['source_id']: bool(r['enabled']) for r in conn.execute('SELECT * FROM collection_settings')}
            custom = [custom_descriptor(dict(r)) for r in conn.execute('SELECT * FROM custom_sources ORDER BY rowid')]
        return [dict(s, enabled=settings.get(s['id'], s['default_enabled'])) for s in (*CATALOG, *custom)]

    def collection_source(self, source_id):
        for source in self.collection_sources():
            if source['id'] == source_id:
                return source
        raise FeedError('Không tìm thấy nguồn theo dõi đã lưu.')

    def add_source(self, data):
        from .service import ValidationError
        if self.demo or data.get('confirmed') is not True:
            raise ValidationError('Cần xác nhận quyền truy cập và phạm vi trước khi thêm nguồn; không thêm trong bản minh họa.')
        name, kind = data.get('name'), data.get('kind', 'auto')
        if (not isinstance(name, str) or not 2 <= len(name.strip()) <= 120
                or any(ord(c) < 32 for c in name) or kind not in ('auto', 'rss', 'web')):
            raise ValidationError('Tên nguồn cần 2–120 ký tự và loại nguồn phải là RSS/Atom hoặc web.')
        try:
            url = subscription_url(data.get('url'))
            prefix = validate_prefix(data.get('prefix', '')) if kind == 'web' else ''
            key = canonical_url(url)
            with self.connection() as conn:
                if conn.execute('SELECT COUNT(*) FROM custom_sources').fetchone()[0] >= MAX_CUSTOM_SOURCES:
                    raise FeedError(f'Đã đạt giới hạn {MAX_CUSTOM_SOURCES} nguồn tùy chỉnh. Tạm dừng để quản lý nguồn hiện có.')
                duplicate = conn.execute('SELECT id FROM custom_sources WHERE input_url=? OR url_key=?', (key, key)).fetchone()
            if duplicate or any(canonical_url(s['url']) == key for s in CATALOG):
                raise FeedError('Nguồn này đã có trong Nguồn tin. Không thêm trùng; hãy bật nguồn hiện có.')
            detected = discover_source(url, kind, prefix)
            source = custom_descriptor(dict(detected, id='custom-' + secrets.token_hex(16), name=name.strip()))
            detected_key = canonical_url(source['url'])
            # One transaction covers duplicate/count checks and enabling. Network work occurs before it.
            with self.connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                if (conn.execute('SELECT COUNT(*) FROM custom_sources').fetchone()[0] >= MAX_CUSTOM_SOURCES
                        or conn.execute('SELECT id FROM custom_sources WHERE url_key=? OR input_url=?', (detected_key, key)).fetchone()
                        or any(canonical_url(s['url']) == detected_key for s in CATALOG)):
                    raise FeedError('Nguồn đã tồn tại hoặc đã đạt giới hạn nguồn; không thêm bản trùng.')
                conn.execute('INSERT INTO custom_sources VALUES (?,?,?,?,?,?,?,?,?)',
                             (source['id'], source['name'], source['kind'], source['url'], detected_key,
                              key, source['site'], source['prefix'], at()))
                conn.execute('INSERT INTO collection_settings VALUES (?,?,?)', (source['id'], 1, at()))
            return dict(source, enabled=True)
        except FeedError as exc:
            raise ValidationError(str(exc)) from None

    def configure_source(self, source_id, data):
        from .service import ValidationError
        try:
            self.collection_source(source_id)
        except FeedError as exc:
            raise ValidationError(str(exc)) from None
        enabled = data.get('enabled')
        if type(enabled) is not bool or (enabled and data.get('confirmed') is not True):
            raise ValidationError('Cần xác nhận phạm vi nguồn trước khi bật thu thập.')
        if self.demo:
            raise ValidationError('Bản minh họa không bật nguồn thật.')
        with self.connection() as conn:
            conn.execute('INSERT INTO collection_settings VALUES (?,?,?) ON CONFLICT(source_id) '
                         'DO UPDATE SET enabled=excluded.enabled,confirmed_at=excluded.confirmed_at',
                         (source_id, int(enabled), at()))
            if not enabled:
                conn.execute("UPDATE collection_jobs SET status='cancelled',message=?,updated_at=? "
                             "WHERE source_id=? AND status='pending'",
                             ('Đã tắt nguồn. Không chạy tác vụ đang chờ.', at(), source_id))
        return {'ok': True}

    def queue_browser(self, source_id, reason):
        source = self.collection_source(source_id)
        if source['kind'] != 'web':
            raise FeedError('Không dùng trình duyệt để vượt lỗi RSS/API.')
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute("SELECT * FROM collection_jobs WHERE source_id=? AND status IN "
                               "('pending','running','unknown')", (source_id,)).fetchone()
            if row:
                return dict(row)
            cursor = conn.execute("INSERT INTO collection_jobs(source_id,status,reason,message,created_at,updated_at) "
                                  "VALUES (?,'pending',?,?,?,?)", (source_id, reason[:300],
                                  'Chờ kết nối Hermes và xác nhận hạn mức. Chưa gọi AI.', at(), at()))
            return dict(conn.execute('SELECT * FROM collection_jobs WHERE id=?', (cursor.lastrowid,)).fetchone())

    def collection_jobs(self):
        self.recover_collection_jobs()
        with self.connection() as conn:
            return [dict(r) for r in conn.execute('SELECT * FROM collection_jobs ORDER BY id DESC LIMIT 50')]

    def cancel_browser_job(self, job_id):
        from .service import ValidationError
        with self.connection() as conn:
            cursor = conn.execute("UPDATE collection_jobs SET status='cancelled',message=?,updated_at=? "
                                  "WHERE id=? AND status IN ('pending','unknown','failed')",
                                  ('Người dùng đóng tác vụ. Không có bài nào được duyệt hoặc đăng.', at(), job_id))
            if not cursor.rowcount:
                raise ValidationError('Chỉ đóng tác vụ chưa chạy hoặc đã mất dấu; không hủy một lượt đang chạy.')
        return {'ok': True}

    def browser_settings(self):
        from .service import ValidationError
        path = self.data_dir / 'browser-connection.json'
        if not path.is_file():
            raise ValidationError('Chưa kết nối Hermes. Xem docs/THU-THAP-DA-TANG.md; không cần bật để dùng RSS/API/web.')
        try:
            if path.stat().st_size > 16000:
                raise ValueError()
            config = json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(config, dict) or config.get('enabled') is not True or not config.get('model')
                    or config.get('provider') != 'openrouter'
                    or not isinstance(config.get('model'), str) or not config['model'].strip() or len(config['model']) > 200
                    or type(config.get('max_jobs_per_day')) is not int
                    or not 1 <= config['max_jobs_per_day'] <= 3):
                raise ValueError()
            root = Path(config['hermes_root']).resolve()
            if not (root / 'run_agent.py').is_file() or not (root / 'venv/Scripts/python.exe').is_file():
                raise ValueError()
            tools_python()
        except (KeyError, TypeError, ValueError, OSError, FeedError):
            raise ValidationError('Cấu hình Hermes chưa hợp lệ. Không gọi model, không tự đổi nhà cung cấp.') from None
        try:
            key_path = self.data_dir / 'browser-key.txt'
            key = os.environ.get('BANTIN_BROWSER_API_KEY', '').strip()
            if not key and key_path.is_file() and key_path.stat().st_size <= 2000:
                key = key_path.read_text(encoding='utf-8').strip()
            if not key or len(key) > 2000 or any(c.isspace() for c in key):
                raise ValueError()
        except (OSError, ValueError):
            raise ValidationError('Thiếu khóa model dành riêng cho trình duyệt. Không lấy khóa/đăng nhập cá nhân có sẵn.')
        return config, key

    def collection_status(self):
        from .service import ValidationError
        try:
            python = tools_python()
            crawl = {'ready': True, 'message': 'Có môi trường công cụ riêng; xem kết quả từng nguồn để biết lượt đọc thực tế.'}
        except FeedError as exc:
            crawl = {'ready': False, 'message': str(exc)}
        try:
            config, _ = self.browser_settings()
            browser = {'ready': True, 'message': 'Đủ cấu hình; chưa chứng minh kết nối/model hoạt động.',
                       'max_jobs_per_day': config['max_jobs_per_day']}
        except ValidationError as exc:
            browser = {'ready': False, 'message': str(exc)}
        return {'crawl': crawl, 'browser': browser,
                'hermes_detected': bool(shutil.which('hermes')), 'jobs': self.collection_jobs()}

    def collect_non_rss(self, source):
        if source['kind'] == 'api':
            return parse_api(fetch_bytes(source['url'], source), source), []
        with self.connection() as conn:
            known = {r['url'] for r in conn.execute('SELECT url FROM collection_evidence')}
        return collect_web(source, known=known)

    def prepare_browser_job(self, job_id, confirmed=False):
        from .service import ValidationError
        if self.demo or confirmed is not True:
            raise ValidationError('Tác vụ AI cần bạn xác nhận; không chạy trong bản minh họa.')
        config, key = self.browser_settings()
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            job = conn.execute('SELECT * FROM collection_jobs WHERE id=?', (job_id,)).fetchone()
            if not job or job['status'] != 'pending':
                raise ValidationError('Tác vụ không còn ở trạng thái chờ. Không tự chạy lại kết quả chưa rõ.')
            source = next(s for s in self.collection_sources() if s['id'] == job['source_id'])
            if not source['enabled']:
                raise ValidationError('Nguồn đang tắt.')
            if conn.execute("SELECT COUNT(*) FROM collection_jobs WHERE status='running'").fetchone()[0]:
                raise ValidationError('Đang có tác vụ trình duyệt chạy. Vui lòng chờ.')
            # Rolling 24h, persisted across app restarts. Includes unknown attempts.
            used = conn.execute("SELECT COUNT(*) FROM collection_attempts "
                                "WHERE julianday(started_at)>julianday('now','-1 day')").fetchone()[0]
            if used >= config['max_jobs_per_day']:
                raise ValidationError('Đã hết số lượt trình duyệt AI trong 24 giờ. Không tự tăng hạn mức.')
            conn.execute("UPDATE collection_jobs SET status='running',message=?,updated_at=? WHERE id=?",
                         ('Đang chạy tối đa 12 vòng, 180 giây; không duyệt hoặc đăng bài.', at(), job_id))
            conn.execute('INSERT INTO collection_attempts(job_id,started_at) VALUES (?,?)', (job_id, at()))
        return config, key, source

    def run_browser_job(self, job_id, confirmed=False):
        prepared = self.prepare_browser_job(job_id, confirmed)
        return self.run_prepared_browser_job(job_id, prepared)

    def run_prepared_browser_job(self, job_id, prepared):
        from .service import ValidationError
        config, key, source = prepared
        try:
            result = run_worker('hermes', {'source_id': source['id'], 'source': source, 'config': config, 'api_key': key,
                                          'tools_python': tools_python()}, timeout=180,
                                python=str(Path(config['hermes_root']) / 'venv/Scripts/python.exe'))
            pages = result.get('pages')
            if not isinstance(pages, list) or not 1 <= len(pages) <= MAX_PAGES:
                raise FeedError('Agent không có tư liệu trang được xác nhận độc lập.')
            for page in pages:
                validate_worker_page(page, source)
            items = [extract_page(p['html'], p['url'], source, method='hermes-browser-use') for p in pages]
            added = self.ingest(source, items)
            with self.connection() as conn:
                conn.execute("UPDATE collection_jobs SET status='completed',message=?,updated_at=? WHERE id=?",
                             (f"Đã lưu {added['added']} tin, {added['duplicate']} trùng. Chưa tạo/duyệt bài đăng.", at(), job_id))
            return added
        except Exception:
            with self.connection() as conn:
                conn.execute("UPDATE collection_jobs SET status='unknown',message=?,updated_at=? WHERE id=?",
                             ('Chưa xác nhận hoàn tất; có thể đã dùng hạn mức AI. Không tự thử lại. Kiểm tra nhà cung cấp.', at(), job_id))
            raise ValidationError('Tác vụ chưa có kết quả được xác nhận. Đã giữ trạng thái mất dấu, không tự chạy lại.') from None
