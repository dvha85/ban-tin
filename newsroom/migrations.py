"""Versioned, additive SQLite migrations for the local newsroom."""
import secrets
import sqlite3
from contextlib import closing

CURRENT_SCHEMA = 4

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


def migrate(conn, data_dir):
    version = conn.execute('PRAGMA user_version').fetchone()[0]
    if version not in (0, 1, 2, 3, CURRENT_SCHEMA):
        raise RuntimeError('Dữ liệu thuộc phiên bản mới hơn. Không tự hạ cấp.')
    if version == CURRENT_SCHEMA:
        return
    if version in (1, 2, 3):
        folder = data_dir / 'backups'
        folder.mkdir(exist_ok=True)
        label = {1: 'pre-v02', 2: 'pre-v03', 3: 'pre-v04'}[version]
        backup_path = folder / f'{label}-{secrets.token_hex(4)}.sqlite3'
        with closing(sqlite3.connect(backup_path)) as backup:
            conn.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Bản sao lưu trước nâng cấp không toàn vẹn; đã dừng nâng cấp.')
    try:
        conn.execute('BEGIN IMMEDIATE')
        # Recheck under the write lock so another process cannot migrate in parallel.
        if conn.execute('PRAGMA user_version').fetchone()[0] != version:
            raise RuntimeError('Dữ liệu vừa được nâng cấp bởi tiến trình khác; hãy mở lại ứng dụng.')
        for statement in SCHEMA:
            conn.execute(statement)
        conn.execute(f'PRAGMA user_version={CURRENT_SCHEMA}')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
