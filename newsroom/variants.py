"""Platform-specific revisions, approval snapshots, and exact exports."""
import hashlib
import json
import re

from .bulletins import _json, _now, _text
from .social_formats import LIMITS, POLICY_VERSION, RENDERER_VERSION, render_segments, split_segments

CHECKS = ('sources', 'facts', 'original', 'rights', 'claims')
UNRESOLVED = re.compile(r'\[(?:CẦN KIỂM TRA|CHƯA XÁC MINH)\]', re.I)


def snapshot_hash(snapshot):
    return hashlib.sha256(_json(snapshot).encode('utf-8')).hexdigest()


class VariantMixin:
    def _variant(self, conn, variant_id):
        from .service import ValidationError
        row = conn.execute('SELECT * FROM content_variants WHERE id=?', (variant_id,)).fetchone()
        if not row:
            raise ValidationError('Không tìm thấy phiên bản nền tảng.')
        result = dict(row)
        result.update(json.loads(result.pop('payload')))
        parent = conn.execute('SELECT revision FROM bulletins WHERE id=?', (result['bulletin_id'],)).fetchone()
        result['needs_update'] = result['locked_at'] is None and result['bulletin_revision'] != parent['revision']
        result['policy_stale'] = False
        result['publication_progress'] = None
        if result['approval_id'] is not None:
            approval = conn.execute('SELECT snapshot FROM variant_approvals WHERE id=? AND variant_id=?',
                                    (result['approval_id'], variant_id)).fetchone()
            if approval:
                snapshot = json.loads(approval['snapshot'])
                result['policy_stale'] = (snapshot.get('policy_version') != POLICY_VERSION or
                                          snapshot.get('renderer_version') != RENDERER_VERSION)
                active = conn.execute('''SELECT COUNT(*) FROM publications
                    WHERE variant_id=? AND approval_id=? AND active=1''',
                    (variant_id, result['approval_id'])).fetchone()[0]
                result['publication_progress'] = {'active': active, 'total': len(snapshot['rendered']['posts'])}
                # Older databases can retain partial status after the last cancellation.
                if result['locked_at'] and active == 0 and result['status'] == 'partially_recorded':
                    result['status'] = 'approved'
        return result

    def variant(self, variant_id):
        with self.connection() as conn:
            return self._variant(conn, variant_id)

    def variants(self, bulletin_id):
        with self.connection() as conn:
            self._bulletin(conn, bulletin_id)
            return [self._variant(conn, row['id']) for row in conn.execute(
                'SELECT id FROM content_variants WHERE bulletin_id=? ORDER BY id', (bulletin_id,))]

    def _locked_variant(self, conn, variant_id, revision):
        from .service import Conflict
        variant = self._variant(conn, variant_id)
        if type(revision) is not int or revision != variant['revision']:
            raise Conflict('Phiên bản đã thay đổi ở cửa sổ khác. Hãy giữ phần đang sửa và tải lại.')
        return variant

    def create_variant(self, bulletin_id, data):
        from .service import ValidationError
        platform = data.get('platform')
        if platform not in LIMITS:
            raise ValidationError('Hãy chọn Facebook, Threads hoặc X.')
        account = _text(data.get('account_label', ''), 'Tên tài khoản / Page', 120)
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            bulletin = self._locked_bulletin(conn, bulletin_id, data.get('bulletin_revision'))
            payload = {'segments': [{'text': '', 'item_ids': [item['id'] for item in bulletin['items']]}],
                       'checks': {key: False for key in CHECKS}}
            at = _now()
            variant_id = conn.execute('''INSERT INTO content_variants
                (bulletin_id,platform,account_label,revision,bulletin_revision,status,payload,created_at,updated_at)
                VALUES (?,?,?,1,?,'draft',?,?,?)''',
                (bulletin_id, platform, account, bulletin['revision'], _json(payload), at, at)).lastrowid
            result = self._variant(conn, variant_id)
            self._bulletin_history(conn, bulletin_id, 'variant', variant_id, 1, 'created', result)
        return result

    def clone_variant(self, variant_id, data):
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            original = self._locked_variant(conn, variant_id, data.get('revision'))
            bulletin = self._bulletin(conn, original['bulletin_id'])
            account = _text(data.get('account_label', original['account_label']), 'Tên tài khoản / Page', 120)
            # Preserve every segment's text. A parent edit may have removed an item
            # or source; never silently substitute another attribution for it.
            items = {item['id']: item for item in bulletin['items']}
            parent_changed = original['bulletin_revision'] != bulletin['revision']
            review = bool(original.get('attribution_review_required'))
            segments = []
            for old in original['segments']:
                retained = [item_id for item_id in old['item_ids'] if item_id in items]
                available = list(dict.fromkeys(source['source_id'] for item_id in retained
                                               for source in items[item_id]['sources']))
                old_sources = old.get('source_ids')
                if old_sources is None:
                    # Implicit "all sources" can mean something different after an edit.
                    sources = [] if parent_changed else available
                    review |= parent_changed
                else:
                    sources = [source_id for source_id in old_sources if source_id in available]
                    review |= len(sources) != len(old_sources)
                review |= len(retained) != len(old['item_ids'])
                segments.append({**old, 'item_ids': retained, 'source_ids': sources})
            payload = {'segments': segments, 'checks': {key: False for key in CHECKS},
                       'attribution_review_required': review}
            at = _now()
            new_id = conn.execute('''INSERT INTO content_variants
                (bulletin_id,platform,account_label,revision,bulletin_revision,status,payload,created_at,updated_at)
                VALUES (?,?,?,1,?,'draft',?,?,?)''',
                (bulletin['id'], original['platform'], account, bulletin['revision'], _json(payload), at, at)).lastrowid
            result = self._variant(conn, new_id)
            self._bulletin_history(conn, bulletin['id'], 'variant', new_id, 1, 'cloned', result)
        return result

    def save_variant(self, variant_id, data):
        from .service import Conflict, ValidationError
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = self._locked_variant(conn, variant_id, data.get('revision'))
            if current['locked_at'] is not None:
                raise Conflict('Phiên bản đã ghi nhận đăng được giữ nguyên. Hãy tạo bản sao để sửa.')
            bulletin = self._bulletin(conn, current['bulletin_id'])
            if current['needs_update'] and data.get('adopt_bulletin_revision') is not True:
                raise Conflict('Bản tin gốc đã đổi. Hãy kiểm tra lại và xác nhận cập nhật phiên bản này.')
            if current.get('attribution_review_required') and data.get('attribution_reviewed') is not True:
                raise ValidationError('Hãy kiểm tra lại các mục và nguồn của bản sao rồi xác nhận trước khi lưu.')
            account = _text(data.get('account_label', current['account_label']), 'Tên tài khoản / Page', 120)
            segments = data.get('segments', current['segments'])
            # Validate structure and attribution; text can remain empty while editing.
            render_segments(current['platform'], segments, bulletin)
            checks = current['checks']
            changed = (account != current['account_label'] or segments != current['segments'] or
                       current['needs_update'] or current['policy_stale'] or
                       current.get('attribution_review_required', False))
            if changed:
                checks = {key: False for key in CHECKS}
            elif 'checks' in data:
                if not isinstance(data['checks'], dict):
                    raise ValidationError('Danh sách kiểm tra không hợp lệ.')
                checks = {key: data['checks'].get(key) is True for key in CHECKS}
            if not changed and checks == current['checks']:
                return current
            payload = {'segments': segments, 'checks': checks}
            conn.execute('''UPDATE content_variants SET account_label=?,revision=revision+1,bulletin_revision=?,
                status='draft',approval_id=NULL,payload=?,updated_at=? WHERE id=?''',
                (account, bulletin['revision'], _json(payload), _now(), variant_id))
            result = self._variant(conn, variant_id)
            self._bulletin_history(conn, bulletin['id'], 'variant', variant_id, result['revision'], 'saved', result)
        return result

    def preview_variant(self, variant_id, data=None):
        from .service import Conflict
        with self.connection() as conn:
            # Read the variant and its parent from the same SQLite snapshot.
            conn.execute('BEGIN')
            variant = self._variant(conn, variant_id)
            if variant['locked_at'] is not None:
                raise Conflict('Phiên bản đã ghi nhận được xem theo bản duyệt lịch sử, không dựng lại từ bản tin hiện tại.')
            bulletin = self._bulletin(conn, variant['bulletin_id'])
            segments = data.get('segments', variant['segments']) if data is not None else variant['segments']
            result = render_segments(variant['platform'], segments, bulletin)
            result['needs_update'] = variant['needs_update']
            result['omitted_item_ids'] = [item['id'] for item in bulletin['items']
                                          if not any(item['id'] in post['item_ids'] for post in result['posts'])]
            return result

    def split_variant(self, variant_id, data):
        from .service import Conflict
        with self.connection() as conn:
            variant = self._locked_variant(conn, variant_id, data.get('revision'))
            if variant['locked_at'] is not None or variant['needs_update']:
                raise Conflict('Phiên bản đã khóa hoặc bản tin gốc đã thay đổi; hãy kiểm tra trước khi chia.')
            bulletin = self._bulletin(conn, variant['bulletin_id'])
            segments = split_segments(variant['platform'], data.get('segments', variant['segments']), bulletin)
            return {'segments': segments, 'preview': render_segments(variant['platform'], segments, bulletin)}

    def approve_variant(self, variant_id, data):
        from .service import Conflict, ValidationError
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            variant = self._locked_variant(conn, variant_id, data.get('revision'))
            if variant['locked_at'] is not None or variant['needs_update']:
                raise Conflict('Phiên bản đã khóa hoặc bản tin gốc đã thay đổi.')
            if variant['policy_stale']:
                raise ValidationError('Quy tắc đầu ra đã đổi. Hãy lưu phiên bản, kiểm tra và xác nhận lại trước khi duyệt.')
            if variant.get('attribution_review_required'):
                raise ValidationError('Bản sao cần được kiểm tra lại mục và nguồn trước khi duyệt.')
            bulletin = self._bulletin(conn, variant['bulletin_id'])
            rendered = render_segments(variant['platform'], variant['segments'], bulletin)
            if not variant['account_label'] or not rendered['valid']:
                raise ValidationError('Cần tên tài khoản và nội dung từng đoạn trong giới hạn.')
            if not all(variant['checks'].get(key) is True for key in CHECKS):
                raise ValidationError('Hãy hoàn thành cả 5 mục kiểm tra của phiên bản.')
            used_ids = {item_id for post in rendered['posts'] for item_id in post['item_ids']}
            for item in bulletin['items']:
                if item['id'] in used_ids and (not item['body'] or not item['verified']
                        or len(item['verification_note']) < 20 or UNRESOLVED.search(item['body'])):
                    raise ValidationError('Mỗi mục được dùng cần nội dung, ghi chú kiểm chứng và xác nhận đã kiểm tra.')
                if item['id'] in used_ids and (not item.get('claims') or any(
                        not claim.get('checked') or not claim.get('evidence', '').strip()
                        or UNRESOLVED.search(claim.get('text', '')) or UNRESOLVED.search(claim.get('evidence', ''))
                        for claim in item['claims'])):
                    raise ValidationError('Mỗi mục cần các khẳng định đã kiểm tra cùng nguồn đối chiếu hoặc lý do.')
            if any(UNRESOLVED.search(post['text']) for post in rendered['posts']):
                raise ValidationError('Bài còn dấu cần kiểm tra hoặc chưa xác minh.')
            snapshot = {'bulletin': bulletin, 'platform': variant['platform'], 'account_label': variant['account_label'],
                        'segments': variant['segments'], 'checks': variant['checks'], 'rendered': rendered,
                        'policy_version': POLICY_VERSION, 'renderer_version': RENDERER_VERSION}
            at = _now()
            approval_id = conn.execute('''INSERT INTO variant_approvals
                (variant_id,variant_revision,bulletin_revision,snapshot,approved_hash,policy_version,created_at)
                VALUES (?,?,?,?,?,?,?)''', (variant_id, variant['revision'], bulletin['revision'], _json(snapshot),
                                            snapshot_hash(snapshot), POLICY_VERSION, at)).lastrowid
            conn.execute("UPDATE content_variants SET status='approved',approval_id=?,revision=revision+1,updated_at=? WHERE id=?",
                         (approval_id, at, variant_id))
            result = self._variant(conn, variant_id)
            self._bulletin_history(conn, bulletin['id'], 'variant', variant_id, result['revision'], 'approved', snapshot)
        return result

    def _approved_variant(self, conn, variant, archive=False):
        from .service import ValidationError
        row = conn.execute('SELECT * FROM variant_approvals WHERE id=? AND variant_id=?',
                           (variant['approval_id'], variant['id'])).fetchone()
        if not row or variant['status'] not in ('approved', 'partially_recorded', 'recorded'):
            raise ValidationError('Chỉ xuất được phiên bản đã duyệt.')
        snapshot = json.loads(row['snapshot'])
        if snapshot_hash(snapshot) != row['approved_hash']:
            raise ValidationError('Bản duyệt không khớp nội dung đã lưu.')
        if not archive:
            if variant['locked_at'] is None and variant['needs_update']:
                raise ValidationError('Bản tin gốc đã thay đổi; cần kiểm tra và duyệt lại.')
            if snapshot['policy_version'] != POLICY_VERSION or snapshot['renderer_version'] != RENDERER_VERSION:
                raise ValidationError('Quy tắc đầu ra đã đổi; hãy tạo bản sao và duyệt lại.')
        return snapshot

    def export_variant(self, variant_id, archive=False):
        with self.connection() as conn:
            # A concurrent edit can invalidate an approval between SELECTs.
            # Pin the variant, parent revision, and approval to one snapshot.
            conn.execute('BEGIN')
            variant = self._variant(conn, variant_id)
            snapshot = self._approved_variant(conn, variant, archive=archive)
            result = {'platform': snapshot['platform'], 'account_label': snapshot['account_label'],
                      'policy_version': snapshot['policy_version'], 'archive': archive,
                      'posts': [post['text'] for post in snapshot['rendered']['posts']]}
            if archive:
                # Provenance is part of the hash-verified historical snapshot,
                # not the possibly changed current bulletin.
                result['items'] = [{'id': item['id'], 'title': item['title'],
                                    'sources': [{'source_id': source['source_id'], 'url': source['url']}
                                                for source in item['sources']]}
                                   for item in snapshot['bulletin']['items']]
                result['rendered_posts'] = snapshot['rendered']['posts']
                result['checks'] = snapshot['checks']
            return result
