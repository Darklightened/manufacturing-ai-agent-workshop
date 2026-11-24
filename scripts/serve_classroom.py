#!/usr/bin/env python3
"""Finite, manifest-only workshop server. Loopback by default; no upload/API routes."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.server
import io
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import signal
import socket
import stat
import threading
import time
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAMES = frozenset(f'workshop-{name}.zip' for name in ('source', 'media', 'offline', 'handouts'))
PACKAGE_ROUTE = 'classroom-downloads/'
RELEASE_LINK = re.compile(r'https://github\.com/Darklightened/manufacturing-ai-agent-workshop/releases/download/[^/\s\"\'<>]+/(workshop-(?:source|media|offline|handouts)\.zip)')


def checked_parts(name: str) -> tuple[str, ...]:
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('invalid relative path')
    parts = name.split('/')
    if any(not p or p.startswith('.') for p in parts) or PurePosixPath(name).is_absolute():
        raise ValueError('hidden, traversal or empty path component')
    return tuple(parts)


@contextmanager
def open_beneath(root: Path, parts: tuple[str, ...]):
    """Open each component relative to a directory FD; never follow symlinks."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(file_fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('not a regular file')
            yield stream
    finally:
        os.close(fd)


def fingerprint(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


@dataclass(frozen=True)
class Entry:
    root: Path
    parts: tuple[str, ...]
    size: int
    digest: str
    identity: tuple


def verify_entry(root: Path, name: str, size: int, digest: str) -> Entry:
    parts = checked_parts(name)
    if type(size) is not int or size < 0 or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('invalid size or SHA256')
    with open_beneath(root, parts) as stream:
        before = os.fstat(stream.fileno())
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
    if size != before.st_size or actual != digest or fingerprint(before) != fingerprint(after):
        raise ValueError(f'build/package checksum mismatch: {name}')
    return Entry(root, parts, size, digest, fingerprint(after))


class Catalogue:
    def __init__(self, directory: Path, package_root: Path | None = None):
        self.directory = Path(directory).resolve(strict=True)
        with open_beneath(self.directory, ('build-manifest.json',)) as stream:
            manifest = json.load(stream)
        if manifest.get('schema') != 'seminar.build.v3' or not isinstance(manifest.get('files'), list):
            raise ValueError('expected a reviewed seminar.build.v3 directory')
        self.entries: dict[str, Entry] = {}
        for row in manifest['files']:
            name = row['path']
            if name in self.entries or name.startswith(PACKAGE_ROUTE):
                raise ValueError('duplicate or reserved build path')
            self.entries[name] = verify_entry(self.directory, name, row['bytes'], row['sha256'])
        if 'index.html' not in self.entries:
            raise ValueError('build has no index.html')
        self.packages = False
        if package_root is not None:
            package_root = Path(package_root).resolve(strict=True)
            with open_beneath(package_root, ('packages-manifest.json',)) as stream:
                packages = json.load(stream)
            if packages.get('schema') != 'seminar.packages.v3':
                raise ValueError('expected seminar.packages.v3')
            rows = packages.get('packages', [])
            if len(rows) != 4 or {r['file'] for r in rows} != PACKAGE_NAMES:
                raise ValueError('exactly the four reviewed workshop ZIPs are required')
            for row in rows:
                self.entries[PACKAGE_ROUTE + row['file']] = verify_entry(package_root, row['file'], row['bytes'], row['sha256'])
            self.packages = True
        self.downloads: bytes | None = None
        if self.packages and 'downloads.html' in self.entries:
            entry = self.entries['downloads.html']
            with self.open(entry) as stream:
                text = stream.read().decode('utf-8')
            self.downloads = RELEASE_LINK.sub(lambda m: '/' + PACKAGE_ROUTE + m[1], text).encode('utf-8')

    @contextmanager
    def open(self, entry: Entry):
        with open_beneath(entry.root, entry.parts) as stream:
            if fingerprint(os.fstat(stream.fileno())) != entry.identity:
                raise ValueError('verified file changed; restart after rebuilding')
            yield stream


def requested_name(target: str) -> str:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith('/'):
        raise ValueError('invalid target')
    path = unquote(parsed.path, encoding='utf-8', errors='strict')
    if path == '/':
        return 'index.html'
    name = path[1:]
    checked_parts(name)
    return name


def byte_range(header: str | None, size: int):
    if header is None:
        return 0, size - 1, False
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header.strip())
    if not match or not any(match.groups()) or not size:
        raise ValueError('invalid or unsatisfiable range')
    first, last = match.groups()
    if first:
        start, end = int(first), min(int(last), size - 1) if last else size - 1
    else:
        length = int(last)
        if not length:
            raise ValueError('empty suffix range')
        start, end = max(0, size - length), size - 1
    if start > end or start >= size:
        raise ValueError('unsatisfiable range')
    return start, end, True


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'ClassroomStatic/1'
    sys_version = ''

    def parse_request(self):
        if not super().parse_request():
            return False
        if self.requestline.split()[1].startswith('//'):
            self.send_error(404, 'Not found')
            return False
        return True

    def log_message(self, format, *args):
        pass  # No student IP, path, query, submitted form or body logs.

    def send_response(self, code, message=None):
        with self.server.stats_lock:
            self.server.status_counts[code] = self.server.status_counts.get(code, 0) + 1
        return super().send_response(code, message)

    def end_headers(self):
        self.send_header('X-Classroom-Origin', 'static-v1')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        super().end_headers()

    def do_GET(self):
        self.send_asset(head=False)

    def do_HEAD(self):
        self.send_asset(head=True)

    def do_POST(self):
        self.send_error(405, 'Only GET and HEAD are available')

    do_PUT = do_POST
    do_DELETE = do_POST
    do_PATCH = do_POST
    do_OPTIONS = do_POST

    def send_asset(self, head):
        headers_sent = False
        try:
            name = requested_name(self.path)
        except (ValueError, UnicodeError):
            self.send_error(404, 'Not found')
            return
        entry = self.server.catalogue.entries.get(name)
        if entry is None:
            self.send_error(404, 'Not found')
            return
        memory = self.server.catalogue.downloads if name == 'downloads.html' else None
        try:
            with self.server.catalogue.open(entry) as source:
                if memory is not None:
                    source = io.BytesIO(memory)
                size = len(memory) if memory is not None else entry.size
                digest = hashlib.sha256(memory).hexdigest() if memory is not None else entry.digest
                try:
                    start, end, partial = byte_range(self.headers.get('Range'), size)
                except (ValueError, OverflowError):
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                self.send_response(206 if partial else 200)
                mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
                if name.endswith('.wasm'):
                    mime = 'application/wasm'
                elif name.endswith('.mjs'):
                    mime = 'text/javascript'
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(end - start + 1))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('ETag', '"' + digest + '"')
                if name.startswith(PACKAGE_ROUTE):
                    self.send_header('Content-Disposition', 'attachment; filename="' + name.split('/')[-1] + '"')
                if partial:
                    self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.end_headers()
                headers_sent = True
                if not head:
                    source.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        block = source.read(min(65536, remaining))
                        if not block:
                            break
                        self.wfile.write(block)
                        remaining -= len(block)
        except (OSError, ValueError):
            # No path or filesystem details are returned. Failed integrity is held closed.
            if not headers_sent:
                try:
                    self.send_error(503, 'Verified asset unavailable')
                except OSError:
                    pass
            self.close_connection = True


class ClassroomServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True

    def __init__(self, address, catalogue: Catalogue, max_connections=128, timeout=15):
        self.catalogue = catalogue
        self.limits = threading.BoundedSemaphore(max_connections)
        self.request_timeout = timeout
        self.stats_lock = threading.Lock()
        self.status_counts = {}
        super().__init__(address, Handler)

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(self.request_timeout)
        return request, address

    def process_request(self, request, client_address):
        if not self.limits.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nX-Classroom-Origin: static-v1\r\nConnection: close\r\n\r\n')
            except OSError:
                pass
            with self.stats_lock:
                self.status_counts[503] = self.status_counts.get(503, 0) + 1
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.limits.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.limits.release()

    def handle_error(self, request, client_address):
        pass

    def serve_for(self, seconds):
        timer = threading.Timer(seconds, self.shutdown)
        timer.daemon = True
        timer.start()
        try:
            self.serve_forever(poll_interval=0.1)
        finally:
            timer.cancel()
            self.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8921)
    parser.add_argument('--directory', type=Path, default=ROOT / 'dist')
    parser.add_argument('--hours', type=float, default=72)
    parser.add_argument('--max-connections', type=int, default=128)
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--with-packages', action='store_true')
    parser.add_argument('--package-root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    if not 0 < args.hours <= 168 or not 1 <= args.max_connections <= 256 or not 1 <= args.timeout <= 60:
        parser.error('hours must be (0,168], connections1–256 and timeout1–60 seconds')
    if not 0 <= args.port <= 65535:
        parser.error('port must be0–65535')
    catalogue = Catalogue(args.directory, args.package_root if args.with_packages else None)
    server = ClassroomServer((args.host, args.port), catalogue, args.max_connections, args.timeout)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start())
    expiry = datetime.fromtimestamp(time.time() + args.hours * 3600, timezone.utc).isoformat()
    print(json.dumps({'state': 'ready', 'pid': os.getpid(), 'bind': args.host, 'port': server.server_port,
                      'directory': str(catalogue.directory), 'manifest_files': len(catalogue.entries),
                      'local_packages': catalogue.packages, 'expires_utc': expiry,
                      'public_reachability': 'unverified; binding is not NAT/firewall admission'}), flush=True)
    server.serve_for(args.hours * 3600)
    print(json.dumps({'state': 'stopped', 'status_counts': server.status_counts}), flush=True)


if __name__ == '__main__':
    main()
