import http.cookiejar
import json
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from newsroom.__main__ import main
from newsroom.service import Newsroom


class StartupTests(unittest.TestCase):
    def test_occupied_port_does_not_create_or_migrate_store(self):
        with tempfile.TemporaryDirectory() as parent, socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            port = listener.getsockname()[1]
            data_dir = Path(parent) / 'new-store'
            result = subprocess.run(
                [sys.executable, '-m', 'newsroom', '--data-dir', str(data_dir),
                 '--port', str(port), '--no-browser', '--no-refresh'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(data_dir.exists(), 'An unavailable port must not create a store')

    def test_occupied_port_leaves_legacy_fixture_unchanged(self):
        with tempfile.TemporaryDirectory() as parent, socket.socket() as listener:
            data_dir = Path(parent) / 'store'
            room = Newsroom(data_dir)
            with room.connection() as conn:
                for table in ('publication_metrics', 'publication_events', 'publications', 'variant_approvals',
                              'content_variants', 'bulletin_items', 'bulletin_history', 'bulletins'):
                    conn.execute('DROP TABLE ' + table)
                conn.execute('PRAGMA user_version=3')
            db = data_dir / 'bantin.sqlite3'
            before = db.read_bytes()
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            result = subprocess.run(
                [sys.executable, '-m', 'newsroom', '--data-dir', str(data_dir),
                 '--port', str(listener.getsockname()[1]), '--no-browser', '--no-refresh'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(db.read_bytes(), before)
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertFalse((data_dir / 'backups').exists())

    def test_failed_store_initialization_releases_reserved_port(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        with patch.object(sys, 'argv', ['newsroom', '--port', str(port), '--no-browser']), \
             patch('newsroom.__main__.Newsroom', side_effect=RuntimeError('fixture failure')):
            with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
                main()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))

    def test_backup_command_does_not_require_a_free_server_port(self):
        with tempfile.TemporaryDirectory() as parent, socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            data_dir = Path(parent) / 'store'
            result = subprocess.run(
                [sys.executable, '-m', 'newsroom', '--data-dir', str(data_dir),
                 '--port', str(listener.getsockname()[1]), '--backup'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(list((data_dir / 'backups').glob('*.sqlite3')))

    def test_server_starts_and_serves_a_new_isolated_store(self):
        with tempfile.TemporaryDirectory() as parent:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            data_dir = Path(parent) / 'store'
            process = subprocess.Popen(
                [sys.executable, '-m', 'newsroom', '--data-dir', str(data_dir),
                 '--port', str(port), '--no-browser', '--no-refresh'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 10
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                while True:
                    try:
                        with opener.open(f'http://127.0.0.1:{port}/', timeout=1) as response:
                            self.assertEqual(response.status, 200)
                        with opener.open(f'http://127.0.0.1:{port}/api/state', timeout=1) as response:
                            state = json.load(response)
                        self.assertEqual(Path(state['data_dir']), data_dir)
                        break
                    except (urllib.error.URLError, TimeoutError):
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail('Server did not start on the isolated store')
                        time.sleep(0.05)
                self.assertTrue((data_dir / 'bantin.sqlite3').is_file())
            finally:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
