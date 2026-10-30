"""Native Windows checks: only disposable test processes; no network/model calls."""
import ctypes
import os
import subprocess
import sys
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows JobObject/watchdog acceptance')
class WorkerLifetimeTests(unittest.TestCase):
    def wait_handle(self, pid):
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        self.assertTrue(handle)
        return kernel, handle

    def test_terminating_worker_closes_only_owned_descendants(self):
        script = ('import subprocess,sys,time; from newsroom.collect_worker import own_process_tree; '
                  'own_process_tree(); child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                  'print(child.pid,flush=True); time.sleep(60)')
        worker = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.PIPE, text=True)
        handle = None
        try:
            pid = int(worker.stdout.readline().strip())
            kernel, handle = self.wait_handle(pid)
            worker.terminate()
            worker.wait(timeout=5)
            self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0)
        finally:
            if worker.poll() is None:
                worker.terminate()
                worker.wait(timeout=5)
            worker.stdout.close()
            if handle:
                kernel.CloseHandle(handle)

    def test_watchdog_stops_after_parent_exit(self):
        parent = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        script = ('import time; from newsroom.collect_worker import own_process_tree,watch_parent; '
                  f'own_process_tree(); watch_parent({parent.pid}); print("ready",flush=True); time.sleep(60)')
        watcher = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(watcher.stdout.readline().strip(), 'ready')
            parent.terminate()
            parent.wait(timeout=5)
            self.assertEqual(watcher.wait(timeout=5), 7)
        finally:
            for process in (watcher, parent):
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
            watcher.stdout.close()


if __name__ == '__main__':
    unittest.main()
