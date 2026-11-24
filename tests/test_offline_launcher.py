"""Portable launcher checks; stdlib only so these also run on Windows CI."""
import contextlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("offline_launcher", SCRIPTS / "launch_offline.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


def free_port():
    with socket.socket() as sock:
        sock.bind((launcher.HOST, 0))
        return sock.getsockname()[1]


class OfflineLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "한글 실습 (offline backup)"
        self.app = self.root / "app"
        self.app.mkdir(parents=True)
        self.files = {
            "index.html": b"<!doctype html><title>Offline workshop</title>",
            "docs/한글.pdf": b"%PDF-1.7\nworkshop fixture\n%%EOF\n",
            "vendor/worker.mjs": b"export const workshop = true;",
            "vendor/worker.js": b"const workshop = true;",
            "vendor/sql.wasm": b"\x00asm\x01\x00\x00\x00",
            "assets/video.webm": b"0123456789abcdef",
            "assets/video.mp4": b"0123456789abcdef",
            "empty.txt": b"",
        }
        for name, content in self.files.items():
            path = self.app / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (self.app / "build-manifest.json").write_text('{"version":"fixture-v1"}', encoding="utf-8")
        (self.root / "private.txt").write_text("PRIVATE OUTSIDE APP", encoding="utf-8")
        (self.app / ".secret").write_text("PRIVATE DOTFILE", encoding="utf-8")
        (self.app / "list-only").mkdir()
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        for name in ("launch_offline.py", "serve.py"):
            shutil.copyfile(SCRIPTS / name, self.scripts / name)

    @contextlib.contextmanager
    def running(self):
        server = launcher.OfflineServer(self.app, 0)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(3)
            server.server_close()
            self.assertFalse(thread.is_alive())

    def request(self, port, path="/", method="GET", headers=None):
        connection = http.client.HTTPConnection(launcher.HOST, port, timeout=3)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, {name.title(): value for name, value in response.getheaders()}, response.read()
        finally:
            connection.close()

    def command(self, *args):
        # Matches the isolated embedded runtime: no cwd/sys.path assumptions.
        return [sys.executable, "-I", "-X", "utf8", str(self.scripts / "launch_offline.py"), *args]

    def test_static_files_unicode_pdf_wasm_js_and_health(self):
        with self.running() as server:
            port = server.server_port
            self.assertEqual(self.request(port)[2], self.files["index.html"])
            cases = [
                ("/docs/%ED%95%9C%EA%B8%80.pdf?download=1", "docs/한글.pdf", "application/pdf"),
                ("/vendor/sql.wasm", "vendor/sql.wasm", "application/wasm"),
                ("/vendor/worker.mjs", "vendor/worker.mjs", "text/javascript"),
                ("/vendor/worker.js", "vendor/worker.js", "text/javascript"),
                ("/assets/video.webm", "assets/video.webm", "video/webm"),
            ]
            for url, name, mime in cases:
                status, headers, body = self.request(port, url)
                self.assertEqual((status, body), (200, self.files[name]))
                self.assertEqual(headers["Content-Type"], mime)
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            status, headers, body = self.request(port, launcher.HEALTH_PATH)
            self.assertEqual(status, 200)
            identity = json.loads(body)
            self.assertEqual(identity, launcher.identity_for(self.app))
            self.assertEqual(identity["product"], launcher.PRODUCT)
            self.assertNotIn(str(self.root).encode(), body)
            self.assertEqual(headers["Cache-Control"], "no-cache")
            self.assertTrue(launcher.is_our_server(port, identity))
            self.assertFalse(launcher.is_our_server(port, {**identity, "root_id": "other"}))
            head = self.request(port, launcher.HEALTH_PATH, "HEAD")
            self.assertEqual((head[0], head[2]), (200, b""))
            self.assertEqual(int(head[1]["Content-Length"]), len(body))

    def test_byte_ranges_and_head(self):
        with self.running() as server:
            for range_value, expected in [
                ("bytes=2-5", b"2345"), ("bytes=-3", b"def"),
                ("bytes=14-", b"ef"), ("bytes=0-99", b"0123456789abcdef"),
            ]:
                status, headers, body = self.request(server.server_port, "/assets/video.webm", headers={"Range": range_value})
                self.assertEqual((status, body), (206, expected))
                self.assertEqual(int(headers["Content-Length"]), len(expected))
                self.assertIn("/16", headers["Content-Range"])
                head = self.request(server.server_port, "/assets/video.webm", "HEAD", {"Range": range_value})
                self.assertEqual((head[0], head[2], head[1]["Content-Length"]), (206, b"", str(len(expected))))
            for invalid in ["bytes=16-", "bytes=7-3", "bytes=-0", "bytes=-", "bytes=0-1,3-4", "items=0-1"]:
                self.assertEqual(self.request(server.server_port, "/assets/video.webm", headers={"Range": invalid})[0], 416)
            self.assertEqual(self.request(server.server_port, "/empty.txt", headers={"Range": "bytes=0-"})[0], 416)
            self.assertEqual(self.request(server.server_port, "/empty.txt")[2], b"")

    def test_no_directory_listing_or_path_escape(self):
        with self.running() as server:
            for path in [
                "/list-only/", "/docs/", "/.secret", "/../private.txt", "/%2e%2e/private.txt",
                "/docs/../index.html", "/docs/%2e%2e/index.html", "/%252e%252e/private.txt",
                "/docs%5c../private.txt", "/%00index.html", "/vendor//worker.js", "//index.html",
                "/C:/Windows/win.ini", "/index.html:stream", "/runtime/python/python.exe",
                "/scripts/launch_offline.py", "http://127.0.0.1/index.html",
            ]:
                status, _, body = self.request(server.server_port, path)
                self.assertEqual(status, 404, path)
                self.assertNotIn(b"PRIVATE", body)
            self.assertEqual(self.request(server.server_port, headers={"Host": "untrusted.example"})[0], 404)

    def test_symlink_files_and_directory_indexes_are_denied(self):
        try:
            (self.app / "outside.txt").symlink_to(self.root / "private.txt")
            (self.app / "escape").symlink_to(self.root, target_is_directory=True)
            (self.app / "list-only/index.html").symlink_to(self.root / "private.txt")
        except OSError as error:
            self.skipTest(f"Creating symlinks is not permitted on this host: {error}")
        with self.running() as server:
            for path in ("/outside.txt", "/escape/private.txt", "/list-only/"):
                self.assertEqual(self.request(server.server_port, path)[0], 404)

    def test_identity_changes_between_roots_and_bundle_versions(self):
        first = launcher.identity_for(self.app)
        other = self.root / "another-app"
        shutil.copytree(self.app, other)
        second = launcher.identity_for(other)
        self.assertNotEqual(first["root_id"], second["root_id"])
        self.assertEqual(first["bundle_id"], second["bundle_id"])
        (self.app / "build-manifest.json").write_text('{"version":"fixture-v2"}', encoding="utf-8")
        self.assertNotEqual(first["bundle_id"], launcher.identity_for(self.app)["bundle_id"])

    def test_existing_same_root_reopens_without_stopping_server(self):
        with self.running() as server, mock.patch.object(launcher, "APP_ROOT", self.app), mock.patch.object(launcher.webbrowser, "open", return_value=True) as browser, contextlib.redirect_stdout(io.StringIO()):
            result = launcher.main(["--port", str(server.server_port)])
            self.assertEqual(result, 0)
            browser.assert_called_once_with(f"http://127.0.0.1:{server.server_port}/", new=0)
            self.assertEqual(self.request(server.server_port)[0], 200)

    def test_other_root_collision_never_opens_browser_or_switches_port(self):
        other = self.root / "another-app"
        shutil.copytree(self.app, other)
        with self.running() as server, mock.patch.object(launcher, "APP_ROOT", other), mock.patch.object(launcher.webbrowser, "open") as browser, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(launcher.main(["--port", str(server.server_port)]), 2)
            browser.assert_not_called()
            self.assertIn(str(server.server_port), output.getvalue())
            self.assertEqual(self.request(server.server_port)[0], 200)

    def test_unrelated_listener_returns_conflict(self):
        with socket.socket() as listener:
            listener.bind((launcher.HOST, 0))
            listener.listen()
            port = listener.getsockname()[1]
            result = subprocess.run(self.command("--no-browser", "--port", str(port)), cwd=self.temp.name, capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(str(port), result.stdout)

    def test_browser_opens_only_after_http_health(self):
        port = free_port()
        calls = []

        def browser_open(url, new):
            self.assertTrue(launcher.is_our_server(port, launcher.identity_for(self.app)))
            calls.append(url)
            return True

        with mock.patch.object(launcher, "APP_ROOT", self.app), mock.patch.object(launcher.webbrowser, "open", side_effect=browser_open), contextlib.redirect_stdout(io.StringIO()):
            result = launcher.main(["--port", str(port), "--duration-seconds", "0.05"])
        self.assertEqual(result, 0)
        self.assertEqual(calls, [f"http://127.0.0.1:{port}/"])
        self.assertFalse(launcher.is_our_server(port, launcher.identity_for(self.app), timeout=0.1))

    def test_no_browser_option_and_browser_failure_keep_server_working(self):
        with mock.patch.object(launcher, "APP_ROOT", self.app), mock.patch.object(launcher.webbrowser, "open", side_effect=OSError("No browser")) as browser, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(launcher.main(["--no-browser", "--port", str(free_port()), "--duration-seconds", "0.05"]), 0)
            browser.assert_not_called()
            self.assertEqual(launcher.main(["--port", str(free_port()), "--duration-seconds", "0.05"]), 0)
            browser.assert_called_once()
            self.assertIn("Chrome", output.getvalue())

    def test_cli_isolated_runtime_korean_spaced_path_and_finite_cleanup(self):
        port = free_port()
        process = subprocess.Popen(self.command("--no-browser", "--port", str(port), "--duration-seconds", "1.5"), cwd=self.temp.name, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            deadline = time.monotonic() + 5
            while not launcher.is_our_server(port, launcher.identity_for(self.app), timeout=0.1):
                self.assertIsNone(process.poll(), "Launcher exited before readiness")
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.05)
            self.assertEqual(self.request(port, "/vendor/sql.wasm")[1]["Content-Type"], "application/wasm")
            stdout, stderr = process.communicate(timeout=7)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn(f"http://127.0.0.1:{port}/", stdout)
            self.assertFalse(launcher.is_our_server(port, launcher.identity_for(self.app), timeout=0.1))
            # Immediate restart must retain the exact origin, not increment a port.
            result = subprocess.run(self.command("--no-browser", "--port", str(port), "--duration-seconds", "0.05"), cwd=self.temp.name, capture_output=True, text=True, encoding="utf-8", timeout=7)
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            if process.poll() is None:
                process.kill()  # Exact child owned by this test, never a port/PID search.
                process.communicate(timeout=5)

    @unittest.skipIf(os.name == "nt", "Native Windows console lifecycle is exercised by the CMD CI check.")
    def test_sigterm_stops_owned_process_and_releases_port(self):
        port = free_port()
        process = subprocess.Popen(self.command("--no-browser", "--port", str(port)), cwd=self.temp.name, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            deadline = time.monotonic() + 5
            while not launcher.is_our_server(port, launcher.identity_for(self.app), timeout=0.1):
                self.assertIsNone(process.poll())
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.05)
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn("종료", stdout)
            self.assertFalse(launcher.is_our_server(port, launcher.identity_for(self.app), timeout=0.1))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    def test_missing_app_fails_without_traceback(self):
        shutil.rmtree(self.app)
        result = subprocess.run(self.command("--no-browser"), cwd=self.temp.name, capture_output=True, text=True, encoding="utf-8", timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("ZIP", result.stdout)

    def test_invalid_diagnostic_options_are_rejected(self):
        for option, values in [("--port", ["0", "65536", "-1"]), ("--duration-seconds", ["0", "-1", "3601", "nan", "inf"])]:
            for value in values:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    launcher.main([option, value])

    def test_windows_cmd_has_ascii_commands_quoted_paths_and_argument_forwarding(self):
        cmd = (SCRIPTS / "offline_launcher/START_WINDOWS.cmd").read_bytes().decode("ascii")
        self.assertIn('"%~dp0runtime\\python\\python.exe" -I -X utf8 "%~dp0scripts\\launch_offline.py" %*', cmd)
        self.assertIn("DisableDelayedExpansion", cmd)
        for unwanted in ("pip install", "Invoke-WebRequest", "curl ", "Set-ExecutionPolicy", "netsh", "taskkill"):
            self.assertNotIn(unwanted.lower(), cmd.lower())


if __name__ == "__main__":
    unittest.main()
