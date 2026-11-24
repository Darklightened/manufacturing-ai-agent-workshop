#!/usr/bin/env python3
"""Finite read-only HTTP relay to a private SSH loopback forward. No file serving."""
import argparse
import http.client
import http.server
import json
import os
from pathlib import Path
import re
import signal
import socket
import threading
import time
from urllib.parse import unquote, urlsplit

ORIGIN_MARKER = 'static-v1'
UPSTREAM_HOST = '127.0.0.1'
ALLOWED_PREFIXES = ('assets/', 'vendor/', 'packages/', 'scenarios/', 'recordings/', 'slides/', 'docs/', 'data/source_pack/', 'classroom-downloads/')
ALLOWED_FILES = {'', 'index.html', 'downloads.html', 'app.mjs', 'styles.css', 'README.md', 'README.ko.md', 'START_HERE.ko.md', 'DATA_LICENSES.md'}
RESPONSE_HEADERS = ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges', 'Last-Modified', 'ETag', 'Content-Disposition', 'Cache-Control')


def valid_path(raw):
    if len(raw) > 4096 or not raw.startswith('/') or raw.startswith('//'):
        return False
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or parts.fragment:
        return False
    try:
        path = unquote(parts.path, errors='strict')
    except (UnicodeError, ValueError):
        return False
    if any(ord(c) < 32 or ord(c) == 127 for c in path) or '\\' in path or '%' in path:
        return False
    segments = path.strip('/').split('/')
    if any(p.startswith('.') for p in segments):
        return False
    rel = path[1:]
    return rel in ALLOWED_FILES or any(rel.startswith(p) for p in ALLOWED_PREFIXES)


class RelayServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 32

    def __init__(self, address, upstream_port=18921, lifetime_seconds=72*3600, max_connections=32):
        if not 0 < lifetime_seconds <= 168*3600:
            raise ValueError('Lifetime must be positive and at most 168 hours')
        self.upstream_port = upstream_port
        self.deadline = time.monotonic() + lifetime_seconds
        self.expires_epoch = time.time() + lifetime_seconds
        self.slots = threading.BoundedSemaphore(max_connections)
        super().__init__(address, RelayHandler)

    def process_request(self, request, client_address):
        request.settimeout(20)
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        # A disconnected student/video seek is not a fatal server error.
        pass


class RelayHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    server_version = 'ClassroomRelay/1'
    sys_version = ''

    def log_message(self, *_):
        # Do not store student addresses, queries or browser request headers.
        pass

    def do_GET(self):
        self.relay(False)

    def do_HEAD(self):
        self.relay(True)

    def deny_method(self):
        self.send_response(405)
        self.send_header('Allow', 'GET, HEAD')
        self.send_header('Content-Length', '0')
        self.send_header('Connection', 'close')
        self.end_headers()

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_CONNECT = do_TRACE = deny_method

    def send_error(self, code, message=None, explain=None):
        message = {400:'Invalid request',403:'Path not allowed',502:'Workshop origin unavailable',503:'Workshop relay closed'}.get(code, 'Request refused')
        return super().send_error(code, message, explain)

    def relay(self, head):
        if time.monotonic() >= self.server.deadline:
            self.send_error(503); return
        if not valid_path(self.path):
            self.send_error(403); return
        if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length', '0') != '0':
            self.send_error(400); return
        headers = {'Host': f'{UPSTREAM_HOST}:{self.server.upstream_port}', 'Connection':'close'}
        if self.headers.get('Range'):
            val = self.headers['Range']
            if not re.fullmatch(r'bytes=(\d*)-(\d*)', val) or val == 'bytes=-':
                self.send_error(400); return
            headers['Range'] = val
        conn = http.client.HTTPConnection(UPSTREAM_HOST, self.server.upstream_port, timeout=20)
        sent = False
        try:
            conn.request('HEAD' if head else 'GET', self.path, headers=headers)
            response = conn.getresponse()
            # Never relay an unrelated loopback service if the SSH forward is absent.
            if response.getheader('X-Classroom-Origin') != ORIGIN_MARKER:
                self.send_error(502); return
            if response.status not in (200,206,304,400,403,404,405,410,416,429,503):
                self.send_error(502); return
            length = response.getheader('Content-Length')
            if length is None or not length.isdigit() or int(length) > 1024**3:
                self.send_error(502); return
            self.send_response(response.status)
            for name in RESPONSE_HEADERS:
                value = response.getheader(name)
                if value is not None:
                    self.send_header(name, value)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Connection', 'close')
            self.end_headers(); sent = True
            if not head:
                remaining = int(length)
                while remaining and time.monotonic() < self.server.deadline:
                    chunk = response.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk); remaining -= len(chunk)
        except (OSError, http.client.HTTPException, ValueError):
            if not sent:
                self.send_error(502)
        finally:
            conn.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',default='0.0.0.0')
    p.add_argument('--port',type=int,default=18920)
    p.add_argument('--upstream-port',type=int,default=18921)
    p.add_argument('--lifetime-hours',type=float,default=72)
    p.add_argument('--state-file',type=Path)
    args=p.parse_args()
    if not 1<=args.port<=65535 or not 1<=args.upstream_port<=65535:
        p.error('Ports must be between1 and65535')
    server=RelayServer((args.host,args.port),args.upstream_port,args.lifetime_hours*3600)
    server.timeout=.5
    stopping=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopping.set())
    state={'schema':'classroom.relay.v1','pid':os.getpid(),'listen_host':args.host,'listen_port':server.server_port,'upstream_host':UPSTREAM_HOST,'upstream_port':args.upstream_port,'expires_epoch':server.expires_epoch,'status':'listening','external_access_verified':False}
    def record():
        if args.state_file:
            args.state_file.parent.mkdir(parents=True,exist_ok=True)
            temp=args.state_file.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2)+'\n');temp.chmod(0o600);temp.replace(args.state_file)
    record();print(json.dumps(state),flush=True)
    try:
        while not stopping.is_set() and time.monotonic()<server.deadline:server.handle_request()
    finally:
        server.server_close();state['status']='stopped';record()

if __name__=='__main__':main()
