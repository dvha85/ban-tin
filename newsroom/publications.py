"""User-reported publication records; never sends requests to social networks."""
import hashlib
import json
import re
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from .bulletins import _json, _now, _text
from .feeds import canonical_url


def normalize_post_url(platform, value):
    from .service import ValidationError
    try:
        url = canonical_url(value)
        parts = urlsplit(url)
    except (ValueError, TypeError) as exc:
        raise ValidationError('Liên kết bài đăng không hợp lệ.') from exc
    host, path = parts.hostname, parts.path
    if platform == 'facebook':
        valid_host = host in ('facebook.com', 'www.facebook.com', 'm.facebook.com')
        query = parse_qs(parts.query)
        valid_path = (bool(re.fullmatch(r'/[^/]+/posts/[^/]+', path)) or
                      bool(re.fullmatch(r'/share/p/[^/]+', path)) or
                      (path in ('/permalink.php', '/story.php') and bool(query.get('story_fbid'))))
        target_host = 'www.facebook.com'
    elif platform == 'threads':
        valid_host = host in ('threads.net', 'www.threads.net', 'threads.com', 'www.threads.com')
        valid_path = bool(re.fullmatch(r'/@[^/]+/post/[^/]+', path))
        target_host = 'www.threads.com'
    elif platform == 'x':
        valid_host = host in ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com')
        valid_path = bool(re.fullmatch(r'/[A-Za-z0-9_]{1,15}/status/[0-9]+', path))
        target_host = 'x.com'
    else:
        raise ValidationError('Nền tảng không hợp lệ.')
    if not valid_host or not valid_path:
        raise ValidationError('Hãy nhập URL HTTPS của bài đăng đúng nền tảng, không phải URL hồ sơ hoặc trang chủ.')
    # Sharing parameters do not distinguish the post. For Facebook's PHP
    # permalink retain the identifiers required to locate the story/Page.
    query = ''
    if platform == 'facebook' and path in ('/permalink.php', '/story.php'):
        query = urlencode([(key, value) for key in ('story_fbid', 'id') for value in parse_qs(parts.query).get(key, [])])
    return urlunsplit(('https', target_host, path, query, ''))


def _post_identity(platform, url):
    parts = urlsplit(url)
    if platform == 'x':
        return ('x', parts.path.rsplit('/', 1)[-1])
    if platform == 'threads':
        return ('threads', parts.path.rsplit('/', 1)[-1])
    return ('facebook', parts.path.casefold(), parts.query)


def _reported_time(value):
    from .service import ValidationError
    if value in (None, ''):
        return None
    if not isinstance(value, str) or len(value) > 80:
        raise ValidationError('Thời gian đăng không hợp lệ.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ValidationError('Thời gian cần định dạng ISO có múi giờ.') from None
    return parsed.isoformat()


class PublicationMixin:
    def legacy_publication_duplicates(self):
        """Read-only overlay for legacy URLs that can be compared safely."""
        groups = {}
        with self.connection() as conn:
            for row in conn.execute("SELECT id,post_url FROM drafts WHERE post_url IS NOT NULL AND post_url<>'' ORDER BY id"):
                url = row['post_url']
                try:
                    normalized = normalize_post_url('facebook', url)
                    key = ('recognized', _post_identity('facebook', normalized))
                except ValueError:
                    try:
                        parts = urlsplit(canonical_url(url))
                        if parts.hostname not in ('facebook.com', 'www.facebook.com', 'm.facebook.com'):
                            continue
                        key = ('exact', (parts.path, parts.query))
                    except (ValueError, TypeError):
                        continue
                groups.setdefault(key, []).append({'id': row['id'], 'url': url})
        return [{'match': key[0], 'drafts': entries} for key, entries in groups.items() if len(entries) > 1]

    def _publication(self, conn, publication_id):
        from .service import ValidationError
        row = conn.execute('SELECT * FROM publications WHERE id=?', (publication_id,)).fetchone()
        if not row:
            raise ValidationError('Không tìm thấy lượt ghi nhận.')
        return dict(row)

    def publications(self, variant_id):
        with self.connection() as conn:
            self._variant(conn, variant_id)
            records = [dict(row) for row in conn.execute(
                'SELECT * FROM publications WHERE variant_id=? ORDER BY id', (variant_id,))]
            for record in records:
                record['events'] = [dict(row) for row in conn.execute(
                    'SELECT * FROM publication_events WHERE publication_id=? ORDER BY id', (record['id'],))]
                record['metrics'] = [dict(row) for row in conn.execute(
                    'SELECT * FROM publication_metrics WHERE publication_id=? ORDER BY id', (record['id'],))]
            return records

    def _check_url_claim(self, conn, url, platform):
        from .service import Conflict
        identity = _post_identity(platform, url)
        for row in conn.execute('''SELECT p.id, p.url, p.position, v.id AS variant_id, v.bulletin_id, v.platform FROM publications p
                                   JOIN content_variants v ON v.id=p.variant_id WHERE p.active=1'''):
            if row['platform'] != platform:
                continue
            try:
                existing_url = normalize_post_url(platform, row['url'])
            except ValueError:
                continue
            if _post_identity(platform, existing_url) == identity:
                target = {'kind': 'publication', 'bulletin_id': row['bulletin_id'],
                          'variant_id': row['variant_id'], 'publication_id': row['id'], 'position': row['position']}
                raise Conflict(f"Liên kết đã thuộc bản tin #{row['bulletin_id']}, phiên bản #{row['variant_id']}, đoạn {row['position'] + 1} (ghi nhận #{row['id']}).", target)
        if platform != 'facebook':
            return
        for row in conn.execute('SELECT id,post_url FROM drafts WHERE post_url IS NOT NULL'):
            try:
                old = normalize_post_url('facebook', row['post_url'])
            except ValueError:
                continue
            if _post_identity('facebook', old) == identity:
                raise Conflict(f"Liên kết đã thuộc bài cũ #{row['id']}. Hãy kiểm tra nhật ký.",
                               {'kind': 'legacy_draft', 'draft_id': row['id']})

    def _publication_progress(self, conn, variant_id, approval_id):
        variant = self._variant(conn, variant_id)
        snapshot = self._approved_variant(conn, variant, archive=True)
        count = conn.execute('SELECT COUNT(*) FROM publications WHERE variant_id=? AND approval_id=? AND active=1',
                             (variant_id, approval_id)).fetchone()[0]
        if count == 0:
            return 'approved'
        return 'recorded' if count == len(snapshot['rendered']['posts']) else 'partially_recorded'

    def record_publication(self, variant_id, data):
        from .service import Conflict, ValidationError
        key = data.get('idempotency_key')
        position = data.get('position')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', key):
            raise ValidationError('Thiếu mã chống ghi nhận trùng.')
        if type(position) is not int or position < 0:
            raise ValidationError('Số thứ tự đoạn không hợp lệ.')
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            variant = self._variant(conn, variant_id)
            url = normalize_post_url(variant['platform'], data.get('url', ''))
            reported_at = _reported_time(data.get('reported_at'))
            request = {'variant_id': variant_id, 'position': position, 'url': url, 'reported_at': reported_at}
            request_hash = hashlib.sha256(_json(request).encode()).hexdigest()
            existing = conn.execute('SELECT * FROM publications WHERE idempotency_key=?', (key,)).fetchone()
            if existing:
                if existing['request_hash'] != request_hash:
                    raise Conflict('Mã ghi nhận đã được dùng cho dữ liệu khác.')
                return dict(existing)
            variant = self._locked_variant(conn, variant_id, data.get('revision'))
            # After one segment is reported, later reports refer to that same
            # locked historical approval even if the parent/policy has changed.
            snapshot = self._approved_variant(conn, variant, archive=variant['locked_at'] is not None)
            if position >= len(snapshot['rendered']['posts']):
                raise ValidationError('Không có đoạn bài này trong bản duyệt.')
            if conn.execute('SELECT id FROM publications WHERE variant_id=? AND position=? AND active=1',
                            (variant_id, position)).fetchone():
                raise Conflict('Đoạn này đã có liên kết được ghi nhận.')
            self._check_url_claim(conn, url, variant['platform'])
            at = _now()
            publication_id = conn.execute('''INSERT INTO publications
                (variant_id,approval_id,position,url,reported_at,recorded_at,idempotency_key,request_hash)
                VALUES (?,?,?,?,?,?,?,?)''', (variant_id, variant['approval_id'], position, url,
                                            reported_at, at, key, request_hash)).lastrowid
            conn.execute('INSERT INTO publication_events (publication_id,action,payload,at) VALUES (?,?,?,?)',
                         (publication_id, 'reported', _json(request), at))
            conn.execute("UPDATE content_variants SET locked_at=COALESCE(locked_at,?),status='partially_recorded' WHERE id=?",
                         (at, variant_id))
            status = self._publication_progress(conn, variant_id, variant['approval_id'])
            conn.execute('UPDATE content_variants SET status=?,revision=revision+1,updated_at=? WHERE id=?',
                         (status, at, variant_id))
            result = self._publication(conn, publication_id)
            self._bulletin_history(conn, variant['bulletin_id'], 'publication', publication_id,
                                   variant['revision'] + 1, 'reported', result)
        return result

    def correct_publication(self, publication_id, data):
        from .service import Conflict, ValidationError
        reason = _text(data.get('reason', ''), 'Lý do đính chính', 1000)
        if len(reason) < 5:
            raise ValidationError('Hãy ghi lý do đính chính ít nhất 5 ký tự.')
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            publication = self._publication(conn, publication_id)
            variant = self._locked_variant(conn, publication['variant_id'], data.get('revision'))
            if not publication['active']:
                raise Conflict('Lượt ghi nhận này đã được đính chính hoặc hủy.')
            replacement = data.get('url', '')
            new_url = normalize_post_url(variant['platform'], replacement) if replacement else None
            if new_url and _post_identity(variant['platform'], new_url) == _post_identity(
                    variant['platform'], normalize_post_url(variant['platform'], publication['url'])):
                raise ValidationError('Liên kết mới giống liên kết cũ.')
            conn.execute('UPDATE publications SET active=0 WHERE id=?', (publication_id,))
            at = _now()
            conn.execute('INSERT INTO publication_events (publication_id,action,payload,at) VALUES (?,?,?,?)',
                         (publication_id, 'corrected' if new_url else 'cancelled',
                          _json({'reason': reason, 'replacement_url': new_url}), at))
            replacement_id = None
            if new_url:
                self._check_url_claim(conn, new_url, variant['platform'])
                key = 'correction_' + str(publication_id) + '_' + str(variant['revision'])
                request_hash = hashlib.sha256(_json({'url': new_url, 'reason': reason}).encode()).hexdigest()
                replacement_id = conn.execute('''INSERT INTO publications
                    (variant_id,approval_id,position,url,reported_at,recorded_at,idempotency_key,request_hash)
                    VALUES (?,?,?,?,?,?,?,?)''', (variant['id'], publication['approval_id'], publication['position'],
                      new_url, publication['reported_at'], at, key, request_hash)).lastrowid
                conn.execute('INSERT INTO publication_events (publication_id,action,payload,at) VALUES (?,?,?,?)',
                             (replacement_id, 'correction_of', _json({'publication_id': publication_id, 'reason': reason}), at))
            status = self._publication_progress(conn, variant['id'], publication['approval_id'])
            conn.execute('UPDATE content_variants SET status=?,revision=revision+1,updated_at=? WHERE id=?',
                         (status, at, variant['id']))
            result = {'corrected_id': publication_id, 'replacement_id': replacement_id, 'status': status}
            self._bulletin_history(conn, variant['bulletin_id'], 'publication', publication_id,
                                   variant['revision'] + 1, 'corrected', result)
        return result

    def save_publication_metrics(self, publication_id, data):
        from .service import Conflict, ValidationError
        key = data.get('idempotency_key')
        if key is not None and (not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', key)):
            raise ValidationError('Mã chống ghi trùng số liệu không hợp lệ.')
        observed_at = _reported_time(data.get('observed_at'))
        if observed_at is None:
            raise ValidationError('Cần thời điểm quan sát số liệu.')
        values = {}
        for field in ('views', 'likes', 'saves', 'shares', 'followers', 'minutes', 'replies', 'reposts', 'quotes'):
            if field in ('replies', 'reposts', 'quotes') and field not in data:
                continue  # Preserve the legacy response and stored payload shape.
            value = data.get(field)
            if value is not None and (type(value) is not int or not 0 <= value <= 1000000000):
                raise ValidationError('Số liệu phải là số nguyên không âm hoặc để trống.')
            values[field] = value
        values['note'] = _text(data.get('note', ''), 'Ghi chú số liệu', 1000)
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            publication = self._publication(conn, publication_id)
            if key is not None:
                for row in conn.execute('SELECT * FROM publication_metrics WHERE publication_id=?', (publication_id,)):
                    try:
                        stored = json.loads(row['payload'])
                        if not isinstance(stored, dict):
                            raise ValueError('Invalid metric payload')
                    except (ValueError, TypeError):
                        raise ValidationError('Không thể kiểm tra số liệu đã lưu do dữ liệu không hợp lệ.')
                    if stored.get('_idempotency_key') == key:
                        stored.pop('_idempotency_key')
                        if row['observed_at'] != observed_at or stored != values:
                            raise Conflict('Mã số liệu đã được dùng cho dữ liệu khác.')
                        return {'id': row['id'], 'publication_id': publication_id, 'observed_at': observed_at, **stored}
            if not publication['active']:
                raise ValidationError('Không nhập số liệu cho lượt ghi nhận đã hủy.')
            stored_values = {**values, '_idempotency_key': key} if key is not None else values
            metric_id = conn.execute('''INSERT INTO publication_metrics
                (publication_id,observed_at,payload,created_at) VALUES (?,?,?,?)''',
                (publication_id, observed_at, _json(stored_values), _now())).lastrowid
        return {'id': metric_id, 'publication_id': publication_id, 'observed_at': observed_at, **values}
