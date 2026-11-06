"""Versioned, additive SQLite migrations for the local newsroom."""
import sqlite3
from contextlib import closing

CURRENT_SCHEMA = 4

V4_TABLES = ('bulletins', 'bulletin_items', 'content_variants', 'variant_approvals',
             'publications', 'publication_events', 'publication_metrics', 'bulletin_history')
LEGACY_TABLES = ('articles', 'article_sources', 'drafts', 'history', 'source_health', 'metrics',
                 'collection_settings', 'collection_jobs', 'collection_evidence', 'collection_attempts',
                 'custom_sources')

# Statements are executed one at a time in an explicit transaction. In
# particular, do not use executescript(), which can commit a pending transaction.
SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY, title TEXT NOT NULL, title_key TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE, summary TEXT NOT NULL, source_name TEXT NOT NULL,
        published_at TEXT, date_kind TEXT NOT NULL, fetched_at TEXT NOT NULL)''',
    'CREATE INDEX IF NOT EXISTS articles_title_key ON articles(title_key)',
    '''CREATE TABLE IF NOT EXISTS article_sources (
        id INTEGER PRIMARY KEY, article_id INTEGER NOT NULL REFERENCES articles(id),
        url TEXT NOT NULL UNIQUE, title TEXT NOT NULL, summary TEXT NOT NULL,
        source_name TEXT NOT NULL, published_at TEXT, date_kind TEXT NOT NULL,
        retrieved_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY, article_id INTEGER NOT NULL REFERENCES articles(id),
        revision INTEGER NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL,
        approved_hash TEXT, approved_at TEXT, post_url TEXT, published_at TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY, draft_id INTEGER NOT NULL REFERENCES drafts(id),
        action TEXT NOT NULL, snapshot TEXT NOT NULL, at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS source_health (
        source_id TEXT PRIMARY KEY, checked_at TEXT NOT NULL, ok INTEGER NOT NULL,
        message TEXT NOT NULL, added INTEGER NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS metrics (
        draft_id INTEGER PRIMARY KEY REFERENCES drafts(id), saves INTEGER NOT NULL,
        shares INTEGER NOT NULL, followers INTEGER NOT NULL, minutes INTEGER NOT NULL,
        note TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS collection_settings (
        source_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL, confirmed_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS collection_jobs (
        id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, status TEXT NOT NULL,
        reason TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)''',
    '''CREATE UNIQUE INDEX IF NOT EXISTS active_collection_job ON collection_jobs(source_id)
        WHERE status IN ('pending','running','unknown')''',
    '''CREATE TABLE IF NOT EXISTS collection_evidence (
        url TEXT PRIMARY KEY, collection_method TEXT NOT NULL, content_hash TEXT NOT NULL,
        excerpt_hash TEXT NOT NULL, scope TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS collection_attempts (
        id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES collection_jobs(id),
        started_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS custom_sources (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
        url TEXT NOT NULL, url_key TEXT NOT NULL UNIQUE, input_url TEXT NOT NULL,
        site TEXT NOT NULL, prefix TEXT NOT NULL, created_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS bulletins (
        id INTEGER PRIMARY KEY, revision INTEGER NOT NULL, title TEXT NOT NULL,
        introduction TEXT NOT NULL, conclusion TEXT NOT NULL, edition_date TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS bulletin_items (
        id INTEGER PRIMARY KEY, bulletin_id INTEGER NOT NULL REFERENCES bulletins(id),
        article_id INTEGER REFERENCES articles(id), position INTEGER NOT NULL,
        revision INTEGER NOT NULL, payload TEXT NOT NULL,
        UNIQUE(bulletin_id, position), UNIQUE(bulletin_id, article_id))''',
    '''CREATE TABLE IF NOT EXISTS content_variants (
        id INTEGER PRIMARY KEY, bulletin_id INTEGER NOT NULL REFERENCES bulletins(id),
        platform TEXT NOT NULL, account_label TEXT NOT NULL, revision INTEGER NOT NULL,
        bulletin_revision INTEGER NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL,
        approval_id INTEGER, locked_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS variant_approvals (
        id INTEGER PRIMARY KEY, variant_id INTEGER NOT NULL REFERENCES content_variants(id),
        variant_revision INTEGER NOT NULL, bulletin_revision INTEGER NOT NULL,
        snapshot TEXT NOT NULL, approved_hash TEXT NOT NULL, policy_version TEXT NOT NULL,
        created_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS publications (
        id INTEGER PRIMARY KEY, variant_id INTEGER NOT NULL REFERENCES content_variants(id),
        approval_id INTEGER NOT NULL REFERENCES variant_approvals(id), position INTEGER NOT NULL,
        url TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, reported_at TEXT,
        recorded_at TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL)''',
    'CREATE UNIQUE INDEX IF NOT EXISTS active_publication_url ON publications(url) WHERE active=1',
    '''CREATE UNIQUE INDEX IF NOT EXISTS active_publication_position
        ON publications(variant_id, position) WHERE active=1''',
    '''CREATE TABLE IF NOT EXISTS publication_events (
        id INTEGER PRIMARY KEY, publication_id INTEGER NOT NULL REFERENCES publications(id),
        action TEXT NOT NULL, payload TEXT NOT NULL, at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS publication_metrics (
        id INTEGER PRIMARY KEY, publication_id INTEGER NOT NULL REFERENCES publications(id),
        observed_at TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS bulletin_history (
        id INTEGER PRIMARY KEY, bulletin_id INTEGER NOT NULL REFERENCES bulletins(id),
        entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL, revision INTEGER NOT NULL,
        action TEXT NOT NULL, snapshot TEXT NOT NULL, at TEXT NOT NULL)''',
)


def validate_v4_structure(conn):
    """Check the v4 contract without changing the source database."""
    def quote(name):
        return '"' + name.replace('"', '""') + '"'

    def unique_indexes(connection, table):
        result = set()
        for row in connection.execute(f'PRAGMA index_list({quote(table)})'):
            name, unique, partial = row[1], row[2], row[4]
            if not unique:
                continue
            columns = tuple(entry[2] for entry in connection.execute(f'PRAGMA index_info({quote(name)})'))
            where = ''
            if partial:
                sql_row = connection.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (name,)).fetchone()
                sql = sql_row[0] if sql_row else None
                if not sql or ' where ' not in ' '.join(sql.lower().split()):
                    continue
                where = ''.join(' '.join(sql.lower().split()).split(' where ', 1)[1].split())
            result.add((columns, where))
        return result

    with closing(sqlite3.connect(':memory:')) as reference:
        for statement in SCHEMA:
            reference.execute(statement)
        for table in LEGACY_TABLES:
            quoted = quote(table)
            required = {row[1] for row in reference.execute(f'PRAGMA table_info({quoted})')}
            present = {row[1] for row in conn.execute(f'PRAGMA table_info({quoted})')}
            if not required <= present:
                raise ValueError(f'Tệp schema mới thiếu cấu trúc dữ liệu cũ cần thiết: {table}.')
        for table in V4_TABLES:
            quoted = quote(table)
            columns = lambda db: [tuple(row[1:]) for row in db.execute(f'PRAGMA table_info({quoted})')]
            foreign_keys = lambda db: {tuple(row[2:]) for row in db.execute(f'PRAGMA foreign_key_list({quoted})')}
            if (columns(conn) != columns(reference)
                    or not foreign_keys(reference) <= foreign_keys(conn)
                    or not unique_indexes(reference, table) <= unique_indexes(conn, table)):
                raise ValueError(f'Tệp schema mới có cấu trúc hoặc ràng buộc không hợp lệ: {table}.')
    try:
        if conn.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('Tệp sao lưu có dữ liệu vi phạm khóa ngoại.')
    except sqlite3.DatabaseError as exc:
        raise ValueError('Không thể kiểm tra khóa ngoại trong tệp sao lưu.') from exc


def migrate(conn, data_dir):
    version = conn.execute('PRAGMA user_version').fetchone()[0]
    if version not in (0, 1, 2, 3, CURRENT_SCHEMA):
        raise RuntimeError('Dữ liệu thuộc phiên bản mới hơn. Không tự hạ cấp.')
    if version == CURRENT_SCHEMA:
        # Validate an existing v4 store on one read snapshot before startup;
        # never repair or write to an incompatible store here.
        try:
            conn.execute('BEGIN')
            if conn.execute('PRAGMA user_version').fetchone()[0] != CURRENT_SCHEMA:
                raise RuntimeError('Phiên bản dữ liệu vừa thay đổi; hãy mở lại ứng dụng.')
            validate_v4_structure(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return
    original_data_version = conn.execute('PRAGMA data_version').fetchone()[0]
    has_user_tables = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1").fetchone() is not None
    if version in (1, 2, 3) or (version == 0 and has_user_tables):
        folder = data_dir / 'backups'
        folder.mkdir(exist_ok=True)
        label = {0: 'pre-unversioned', 1: 'pre-v02', 2: 'pre-v03', 3: 'pre-v04'}[version]
        from .backup_utils import reserved_backup
        with reserved_backup(folder, f'{label}-', 4) as backup_path:
            with closing(sqlite3.connect(backup_path)) as backup:
                conn.backup(backup)
                if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Bản sao lưu trước nâng cấp không toàn vẹn; đã dừng nâng cấp.')
    try:
        conn.execute('BEGIN IMMEDIATE')
        # Recheck under the write lock so another process cannot migrate in parallel.
        if conn.execute('PRAGMA user_version').fetchone()[0] != version:
            raise RuntimeError('Dữ liệu vừa được nâng cấp bởi tiến trình khác; hãy mở lại ứng dụng.')
        if conn.execute('PRAGMA data_version').fetchone()[0] != original_data_version:
            raise RuntimeError('Dữ liệu vừa thay đổi trong lúc sao lưu; hãy dừng ứng dụng khác và thử lại.')
        for statement in SCHEMA:
            conn.execute(statement)
        # Existing tables may make CREATE IF NOT EXISTS a no-op. Validate the
        # resulting contract before committing the new version marker.
        validate_v4_structure(conn)
        conn.execute(f'PRAGMA user_version={CURRENT_SCHEMA}')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
