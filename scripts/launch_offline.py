#!/usr/bin/env python3
"""Run the extracted Windows workshop ZIP using only bundled Python's stdlib."""
import argparse
import errno
import hashlib
import http.client
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import socket
import threading
import time
from urllib.parse import unquote, urlsplit
import webbrowser


HOST = "127.0.0.1"
DEFAULT_PORT = 8922
PRODUCT = "manufacturing-ai-agent-workshop-offline"
LAUNCHER_VERSION = 1
HEALTH_PATH = "/__workshop_health"
BUNDLE_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BUNDLE_ROOT / "app"

# The official embeddable Python isolates sys.path. Load our one sibling file
# explicitly instead of depending on the current directory or site-packages.
_spec = importlib.util.spec_from_file_location(
    "workshop_static_server", Path(__file__).resolve().with_name("serve.py")
)
_static = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_static)


def identity_for(app_root):
    """Identify the exact extraction without publishing its filesystem path."""
    app_root = Path(app_root).resolve(strict=True)
    if not (app_root / "index.html").is_file():
        raise ValueError("app/index.html is missing; extract the complete ZIP first.")
    manifest = app_root / "build-manifest.json"
    identity_file = manifest if manifest.is_file() else app_root / "index.html"
    return {
        "product": PRODUCT,
        "launcher_version": LAUNCHER_VERSION,
        "root_id": hashlib.sha256(os.fsencode(os.path.normcase(str(app_root)))).hexdigest(),
        "bundle_id": hashlib.sha256(identity_file.read_bytes()).hexdigest(),
    }


class OfflineHandler(_static.Handler):
    """The packaged app is the only public directory; never enumerate files."""
    extensions_map = {
        **_static.Handler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".pdf": "application/pdf",
        ".webm": "video/webm",
        ".mp4": "video/mp4",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(args[2].app_root), **kwargs)

    def log_message(self, format, *args):
        # A console full of asset requests obscures the stop/save instructions.
        pass

    def _public_path(self):
        if self.headers.get("Host") != f"{HOST}:{self.server.server_port}":
            return None
        try:
            if self.requestline.split()[1].startswith("//"):
                return None
            url = urlsplit(self.path)
            if url.scheme or url.netloc or url.fragment or not url.path.startswith("/"):
                return None
            path = unquote(url.path, errors="strict")
            if "\\" in path or "%" in path or ":" in path:
                return None
            if any(ord(char) < 32 or ord(char) == 127 for char in path):
                return None
            parts = path[1:].split("/")
            if parts and not parts[-1]:
                parts.pop()
            if any(not part or part.startswith(".") for part in parts):
                return None
            candidate = self.server.app_root
            for part in parts:
                candidate = candidate / part
                if candidate.is_symlink():
                    return None
            candidate.resolve().relative_to(self.server.app_root)
            if candidate.is_dir():
                for name in ("index.html", "index.htm"):
                    index = candidate / name
                    if index.is_file():
                        if index.is_symlink():
                            return None
                        index.resolve().relative_to(self.server.app_root)
                        break
            return path
        except (ValueError, UnicodeError, OSError):
            return None

    def send_head(self):
        self._range = None
        path = self._public_path()
        if path is None:
            self.send_error(404, "Not found")
            return None
        if path == HEALTH_PATH:
            body = json.dumps(self.server.identity, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return None
        # Parent handler implements normal files, HEAD and single video ranges.
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def end_headers(self):
        self.send_header("X-Workshop-Offline", str(LAUNCHER_VERSION))
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()


class OfflineServer(_static.http.server.ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    # Windows SO_REUSEADDR can let a second process steal a live listener.
    allow_reuse_address = os.name != "nt"

    def __init__(self, app_root, port=DEFAULT_PORT):
        self.app_root = Path(app_root).resolve(strict=True)
        self.identity = identity_for(self.app_root)
        super().__init__((HOST, port), OfflineHandler)

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


def is_our_server(port, expected_identity, timeout=0.5):
    """No redirects, proxies or browser opening before a full identity match."""
    connection = http.client.HTTPConnection(HOST, port, timeout=timeout)
    try:
        connection.request("GET", HEALTH_PATH)
        response = connection.getresponse()
        if response.status != 200 or response.getheader("X-Workshop-Offline") != str(LAUNCHER_VERSION):
            return False
        body = response.read(4097)
        return len(body) <= 4096 and json.loads(body) == expected_identity
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def _open_browser(url, disabled):
    if disabled:
        return
    try:
        if webbrowser.open(url, new=0):
            return
    except (OSError, webbrowser.Error):
        pass
    print("브라우저를 자동으로 열지 못했습니다. 위 주소를 Chrome 또는 Edge에서 여세요.", flush=True)


def _install_windows_close_handler(stop_event, finished_event):
    """Console close/logoff stops our in-process server; never leaves a child."""
    if os.name != "nt":
        return lambda: None
    import ctypes
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

    @callback_type
    def on_console_event(event):
        if event not in (2, 5, 6):  # Python retains normal Ctrl+C/Ctrl+Break.
            return False
        stop_event.set()
        finished_event.wait(3)
        return True

    register = ctypes.windll.kernel32.SetConsoleCtrlHandler
    register.argtypes = [callback_type, ctypes.c_bool]
    register.restype = ctypes.c_bool
    if not register(on_console_event, True):
        return lambda: None

    def remove():
        register(on_console_event, False)

    return remove  # Closure keeps the native callback alive until shutdown.


def _port(value):
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _duration(value):
    seconds = float(value)
    if not math.isfinite(seconds) or not 0 < seconds <= 3600:
        raise argparse.ArgumentTypeError("duration must be greater than 0 and at most 3600 seconds")
    return seconds


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Start without opening a browser (verification).")
    parser.add_argument("--port", type=_port, default=DEFAULT_PORT, help="Explicit diagnostic port; changing it changes browser storage origin.")
    parser.add_argument("--duration-seconds", type=_duration, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    url = f"http://{HOST}:{args.port}/"
    try:
        expected = identity_for(APP_ROOT)
        server = OfflineServer(APP_ROOT, args.port)
    except OSError as error:
        if error.errno == errno.EADDRINUSE or getattr(error, "winerror", None) == 10048:
            if is_our_server(args.port, expected):
                print(f"이미 실행 중인 실습을 엽니다: {url}", flush=True)
                print("기존 실행 창을 유지하고 실습 탭은 하나만 사용하세요.", flush=True)
                _open_browser(url, args.no_browser)
                return 0
            print(f"포트 {args.port}를 다른 프로그램 또는 다른 실습 폴더가 사용 중입니다.", flush=True)
            print("해당 프로그램의 창을 닫은 뒤 다시 실행하세요. 저장 주소를 유지하기 위해 포트를 자동 변경하지 않습니다.", flush=True)
            return 2
        print(f"실습을 시작할 수 없습니다: {error}", flush=True)
        print("ZIP 전체를 압축 해제한 뒤 START_WINDOWS.cmd를 실행하세요.", flush=True)
        return 1
    except ValueError as error:
        print(f"실습 파일을 확인하세요: {error}", flush=True)
        return 1

    stop_event = threading.Event()
    finished_event = threading.Event()
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
    previous_signals = {}
    remove_console_handler = lambda: None

    def stop(signum, frame):
        stop_event.set()

    try:
        for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            signum = getattr(signal, name, None)
            if signum is not None:
                previous_signals[signum] = signal.signal(signum, stop)
        remove_console_handler = _install_windows_close_handler(stop_event, finished_event)
        thread.start()
        deadline = time.monotonic() + 5
        while not is_our_server(args.port, expected):
            if stop_event.is_set() or time.monotonic() >= deadline or not thread.is_alive():
                raise RuntimeError("The local workshop did not become ready.")
            time.sleep(0.05)
        print(f"제조 AI 실습: {url}", flush=True)
        print("실습 중 이 창을 열어 두세요. 종료: Ctrl+C 또는 이 창 닫기.", flush=True)
        print("진행 기록은 현재 PC와 브라우저에 저장됩니다. 옮길 때는 진행 내보내기를 사용하세요.", flush=True)
        _open_browser(url, args.no_browser)
        stop_at = time.monotonic() + args.duration_seconds if args.duration_seconds else None
        while not stop_event.wait(0.25):
            if stop_at is not None and time.monotonic() >= stop_at:
                break
            if not thread.is_alive():
                raise RuntimeError("The local workshop server stopped unexpectedly.")
        return 0
    except (OSError, RuntimeError) as error:
        print(f"실습 서버 오류: {error}", flush=True)
        return 1
    finally:
        if thread.is_alive():
            server.shutdown()
            thread.join(3)
        server.server_close()
        finished_event.set()
        remove_console_handler()
        for signum, previous in previous_signals.items():
            signal.signal(signum, previous)
        print("실습 서버를 종료했습니다. 저장한 브라우저 기록은 유지됩니다.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
