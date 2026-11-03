import argparse
import sqlite3
import threading
import webbrowser
import sys
from contextlib import closing
from pathlib import Path

from .config import default_data_dir, validate_data_dir
from .server import make_server
from .service import Newsroom, now_iso
from .migrations import CURRENT_SCHEMA


def seed_demo(room):
    if room.articles():
        return
    source = {'id': 'demo', 'name': 'MINH HỌA — không phải tin thật'}
    examples = [
        ('MINH HỌA: AI assistant giúp tóm tắt tài liệu như thế nào?', 'ai-assistant',
         'Dữ liệu giả để tập thao tác. Không có sản phẩm hay tính năng nào được xác minh. Không đăng nội dung này.'),
        ('MINH HỌA: Một privacy feature mới trên trình duyệt', 'privacy-feature',
         'Ví dụ minh họa quy trình kiểm chứng tính năng bảo vệ riêng tư. Đây không phải tin thật.'),
        ('MINH HỌA: AI tool cho người làm văn phòng', 'ai-office',
         'Ví dụ để luyện viết bài giải thích lợi ích và giới hạn của công cụ AI. Không sử dụng như nguồn tin thật.'),
    ]
    for title, slug, summary in examples:
        room.ingest(source, [dict(title=title, url=f'https://example.com/demo/{slug}', summary=summary,
                                  published_at=now_iso(), date_kind='published')])


def restore(backup, destination):
    source_path = Path(backup).resolve()
    if not source_path.is_file():
        raise ValueError('Không tìm thấy tệp sao lưu.')
    target_dir = validate_data_dir(destination)
    if target_dir.exists():
        raise ValueError('Chỉ khôi phục sang thư mục MỚI chưa tồn tại; không ghi đè dữ liệu hiện tại.')
    with closing(sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)) as source:
        # Keep validation and the subsequent SQLite backup on one read snapshot.
        # Otherwise another connection can replace the data after validation.
        source.execute('BEGIN')
        if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Tệp sao lưu lỗi toàn vẹn.')
        version = source.execute('PRAGMA user_version').fetchone()[0]
        if version not in (1, 2, 3, CURRENT_SCHEMA):
            raise ValueError('Tệp không đúng phiên bản dữ liệu Bàn tin.')
        tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'articles', 'drafts', 'history', 'article_sources'} <= tables:
            raise ValueError('Tệp không có cấu trúc dữ liệu Bàn tin.')
        if version == CURRENT_SCHEMA and not {'bulletins', 'bulletin_items', 'content_variants',
                                               'variant_approvals', 'publications', 'publication_events',
                                               'publication_metrics', 'bulletin_history'} <= tables:
            raise ValueError('Tệp schema mới thiếu bảng dữ liệu bản tin.')
        target_dir.mkdir(parents=True, exist_ok=False)
        destination_path = target_dir / 'bantin.sqlite3'
        created_file = False
        try:
            # Reserve the file exclusively; never overwrite a file created by
            # another process after the directory was created.
            with destination_path.open('xb'):
                created_file = True
            with closing(sqlite3.connect(destination_path)) as destination_conn:
                source.backup(destination_conn)
                if destination_conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Bản khôi phục không toàn vẹn.')
        except Exception as exc:
            # Remove only the file created above and the directory if empty.
            # Never recursively delete a destination containing other files.
            try:
                if created_file:
                    destination_path.unlink(missing_ok=True)
                target_dir.rmdir()
            except OSError as cleanup_error:
                exc.add_note(f'Không dọn được thư mục khôi phục chưa hoàn tất: {cleanup_error}')
            raise
    print(f'Da khoi phuc vao thu muc moi: {target_dir}')


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError('Can Python 3.11 tro len. Xem README.md de cai dat.')
    parser = argparse.ArgumentParser(description='Ban tin ca nhan — AI trinh duyet tuy chon, khong tu dang bai')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--port', type=int, default=8877)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--no-refresh', action='store_true')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--collect', action='store_true', help='Doc RSS/API/web dang bat mot lan; khong chay AI')
    parser.add_argument('--backup', action='store_true')
    parser.add_argument('--restore', type=Path, help='Tep sao luu; can --data-dir chi thu muc moi')
    args = parser.parse_args()
    if args.restore:
        if not args.data_dir:
            parser.error('--restore can --data-dir chi thu muc moi')
        restore(args.restore, args.data_dir)
        return
    if not 1024 <= args.port <= 65535:
        parser.error('Cong phai tu 1024 den 65535')
    if args.demo and args.data_dir:
        parser.error('Ban demo luon dung thu muc demo rieng; khong nhan --data-dir')
    room = Newsroom(args.data_dir or default_data_dir(args.demo), demo=args.demo)
    if args.backup:
        print(room.backup())
        return
    if args.demo:
        seed_demo(room)
    if args.collect:
        if args.demo:
            parser.error('Ban demo khong doc tin that')
        import json
        print(json.dumps(room.refresh(), ensure_ascii=True, indent=2))
        return
    try:
        server = make_server(room, args.port)
    except OSError:
        print(f'Khong mo duoc cong {args.port}. Ung dung co the da chay; mo http://127.0.0.1:{args.port}/')
        raise SystemExit(1)
    url = f'http://127.0.0.1:{args.port}/'
    print(f'Ban tin dang chay: {url}\nDu lieu: {room.data_dir}')
    print('Giu cua so nay mo. Nhan Ctrl+C de dung. Khong tu dang; AI chi chay khi ban xac nhan rieng.')
    stop = threading.Event()
    if not args.no_refresh and not args.demo:
        def schedule():
            while not stop.is_set():
                server.start_refresh()
                if stop.wait(7200):
                    break
        threading.Thread(target=schedule, daemon=True, name='source-scheduler').start()
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print('\nDa dung. Du lieu da luu van duoc giu lai.')
    finally:
        stop.set()
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, sqlite3.Error, OSError) as exc:
        print(f'Khong the tiep tuc: {exc}')
        raise SystemExit(1)
