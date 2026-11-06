"""Reserve backup files without replacing existing files."""
import secrets
from contextlib import contextmanager


@contextmanager
def reserved_backup(folder, prefix, token_bytes):
    for _ in range(10):
        target = folder / f'{prefix}{secrets.token_hex(token_bytes)}.sqlite3'
        try:
            with target.open('xb'):
                pass
        except FileExistsError:
            continue
        break
    else:
        raise FileExistsError('Không tạo được tên sao lưu mới; hãy thử lại.')
    try:
        yield target
    except BaseException as exc:
        try:
            target.unlink(missing_ok=True)
        except OSError as cleanup_error:
            exc.add_note(f'Không dọn được tệp sao lưu chưa hoàn tất: {cleanup_error}')
        raise
