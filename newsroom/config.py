import os
from pathlib import Path

SOURCES = (
    {'id': 'google', 'name': 'Google — The Keyword', 'url': 'https://blog.google/rss/',
     'site': 'https://blog.google/', 'color': '#4285f4'},
    {'id': 'windows', 'name': 'Windows Blog', 'url': 'https://blogs.windows.com/feed/',
     'site': 'https://blogs.windows.com/', 'color': '#0078d4'},
    {'id': 'apple', 'name': 'Apple Newsroom', 'url': 'https://www.apple.com/newsroom/rss-feed.rss',
     'site': 'https://www.apple.com/newsroom/', 'color': '#555d68'},
    {'id': 'mozilla', 'name': 'Mozilla Blog', 'url': 'https://blog.mozilla.org/en/feed/',
     'site': 'https://blog.mozilla.org/', 'color': '#b44a18'},
)


def default_data_dir(demo=False):
    # Packaged desktop apps can override LOCALAPPDATA. Keep the same location
    # when starting from Codex, Explorer, or a normal Windows terminal.
    base = Path.home() / 'AppData' / 'Local' if os.name == 'nt' else Path.home() / '.local' / 'share'
    return base / ('BanTinLocal-Demo' if demo else 'BanTinLocal')


def validate_data_dir(path):
    path = Path(path).expanduser().resolve()
    if str(path).startswith('\\\\') or any('onedrive' in part.lower() for part in path.parts):
        raise ValueError('Dữ liệu đang chạy phải nằm ngoài OneDrive và ổ mạng. Dùng thư mục mặc định.')
    if path == Path(path.anchor):
        raise ValueError('Không dùng gốc ổ đĩa làm thư mục dữ liệu.')
    return path
