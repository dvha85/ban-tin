"""Generate a synthetic fixture using an extracted a180354 legacy checkout.

Run from that checkout with the output directory as the sole argument. This is
an offline fixture generator; it does not fetch feeds or access social sites.
"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from newsroom.service import Newsroom  # noqa: E402


def main(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='legacy-v3-synthetic-') as directory:
        room = Newsroom(Path(directory))
        drafts = []
        for index in range(3):
            article = room.import_article({'title': f'Tin giả lập {index}',
                'url': f'https://example.com/legacy-{index}',
                'summary': 'Đây là ghi chú giả lập đủ dài để kiểm tra việc giữ nguồn.'})
            draft = room.create_draft(article['id'])
            draft = room.save_draft(draft['id'], {'revision': draft['revision'],
                'title': f'Tiêu đề bản thử nghiệm {index}', 'page_name': 'Page fixture',
                'body': ('Nội dung thử nghiệm, không phải tin thật. ' * 4),
                'angle': 'Giải thích giới hạn của dữ liệu thử.'})
            if index:
                draft = room.save_draft(draft['id'], {'revision': draft['revision'],
                    'checks': {key: True for key in room.CHECKS}})
                draft = room.approve(draft['id'], draft['revision'])
            if index == 2:
                draft = room.mark_published(draft['id'], draft['revision'],
                                            'https://www.facebook.com/fixture/posts/12345')
                room.save_metrics(draft['id'], {'saves': 7, 'shares': 2, 'followers': 0,
                                                'minutes': 30, 'note': 'Số liệu giả lập'})
            drafts.append(draft)
        with room.connection() as conn:
            conn.execute('INSERT INTO custom_sources VALUES (?,?,?,?,?,?,?,?,?)',
                         ('custom-fixture', 'Nguồn fixture', 'rss', 'https://example.com/feed',
                          'https://example.com/feed', 'https://example.com/feed', 'https://example.com', '/',
                          '2026-11-03T00:00:00+00:00'))
            conn.execute('INSERT INTO collection_settings VALUES (?,?,?)',
                         ('custom-fixture', 1, '2026-11-03T00:00:00+00:00'))
        with room.connection() as conn:
            if conn.execute('PRAGMA user_version').fetchone()[0] != 3:
                raise RuntimeError('The generator must run with schema-3 source code.')
            tables = ('articles', 'article_sources', 'drafts', 'history', 'metrics', 'custom_sources', 'collection_settings')
            expected = {table: [dict(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                        for table in tables}
            expected['exports'] = {str(draft['id']): room.export(draft['id']) for draft in drafts if draft['status'] != 'draft'}
            expected['generator_commit'] = 'a180354e52e98a678d093609f9e8f2d37e6cd0a3'
            # iterdump emits the schema and synthetic data; explicitly restore
            # user_version, which SQLite's dump does not include.
            dump = '\n'.join(conn.iterdump()) + '\nPRAGMA user_version=3;\n'
        (output_dir / 'legacy-v3.sql').write_text(dump, encoding='utf-8')
        (output_dir / 'legacy-v3-expected.json').write_text(json.dumps(expected, ensure_ascii=False,
            sort_keys=True, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main(Path(sys.argv[1]))
