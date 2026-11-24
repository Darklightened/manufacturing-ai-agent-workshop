"""CPU-only contract tests; ephemeral loopback ports and temporary fixture files."""
from contextlib import contextmanager, redirect_stderr
import hashlib
import http.client
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest

SPEC = importlib.util.spec_from_file_location('serve_classroom', Path(__file__).resolve().parents[1] / 'scripts/serve_classroom.py')
server_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = server_module
SPEC.loader.exec_module(server_module)


class ClassroomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dist = self.root / 'dist'
        self.dist.mkdir()
        self.files = {
            'index.html': b'<h1>class</h1>',
            'downloads.html': b'<a href="https://github.com/Darklightened/manufacturing-ai-agent-workshop/releases/download/v0.8.4/workshop-offline.zip">download</a>',
            'video.mp4': b'0123456789abcdef',
            'empty.txt': b'',
            'nested/한글.txt': '도면 확인'.encode(),
            'core.mjs': b'export default 1;',
            'core.wasm': b'\x00asm',
        }
        for name, data in self.files.items():
            p = self.dist / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        (self.dist / 'unlisted.txt').write_text('PRIVATE')
        (self.dist / '.secret').write_text('PRIVATE')
        (self.root / 'outside.txt').write_text('PRIVATE')
        self.write_manifest()
        packages = []
        for name in server_module.PACKAGE_NAMES:
            data = ('ZIP fixture ' + name).encode()
            (self.root / name).write_bytes(data)
            packages.append({'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        (self.root / 'packages-manifest.json').write_text(json.dumps({'schema': 'seminar.packages.v3', 'packages': packages}))

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        rows = [{'path': n, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for n, b in self.files.items()]
        (self.dist / 'build-manifest.json').write_text(json.dumps({'schema': 'seminar.build.v3', 'files': rows}))

    @contextmanager
    def running(self, packages=False, connections=8, expiry=60):
        catalogue = server_module.Catalogue(self.dist, self.root if packages else None)
        server = server_module.ClassroomServer(('127.0.0.1', 0), catalogue, connections, timeout=1)
        thread = threading.Thread(target=server.serve_for, args=(expiry,), daemon=True)
        thread.start()
        try:
            yield server
        finally:
            if thread.is_alive():
                server.shutdown()
            thread.join(3)
            server.server_close()
            self.assertFalse(thread.is_alive())

    def request(self, server, path='/', method='GET', headers=None):
        con = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
        con.request(method, path, headers=headers or {})
        res = con.getresponse()
        result = res.status, dict(res.getheaders()), res.read()
        con.close()
        return result

    def test_manifest_only_and_methods(self):
        with self.running() as server:
            self.assertEqual(self.request(server)[2], self.files['index.html'])
            self.assertEqual(self.request(server)[1]['X-Classroom-Origin'], 'static-v1')
            self.assertEqual(self.request(server, '/unlisted.txt')[1]['X-Classroom-Origin'], 'static-v1')
            for path in ['/unlisted.txt', '/.secret', '/nested/', '/build-manifest.json', '/outside.txt', '/classroom-downloads/workshop-offline.zip']:
                self.assertEqual(self.request(server, path)[0], 404, path)
            for method in ['POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']:
                self.assertEqual(self.request(server, '/', method)[0], 405)
            self.assertEqual(self.request(server, '/core.mjs')[1]['Content-Type'], 'text/javascript')
            self.assertEqual(self.request(server, '/core.wasm')[1]['Content-Type'], 'application/wasm')

    def test_path_attacks_and_unicode(self):
        with self.running() as server:
            for path in ['/../outside.txt', '/%2e%2e/outside.txt', '/nested/%2e%2e/index.html', '/nested%5c../outside.txt', '//index.html', '/%00index.html', '/%252e%252e/outside.txt', '/nested//x', 'http://localhost/index.html']:
                self.assertEqual(self.request(server, path)[0], 404, path)
            self.assertEqual(self.request(server, '/nested/%ED%95%9C%EA%B8%80.txt?ignored=1')[2], self.files['nested/한글.txt'])

    def test_head_and_ranges(self):
        with self.running() as server:
            status, headers, body = self.request(server, '/video.mp4', 'HEAD')
            self.assertEqual((status, body, headers['Content-Length']), (200, b'', '16'))
            for value, expected in [('bytes=2-5', b'2345'), ('bytes=-3', b'def'), ('bytes=14-', b'ef'), ('bytes=0-99', self.files['video.mp4'])]:
                status, headers, body = self.request(server, '/video.mp4', headers={'Range': value})
                self.assertEqual((status, body), (206, expected))
                self.assertEqual(int(headers['Content-Length']), len(expected))
                head = self.request(server, '/video.mp4', 'HEAD', {'Range': value})
                self.assertEqual(head[0], 206)
                self.assertEqual(head[2], b'')
                self.assertEqual(head[1]['Content-Length'], headers['Content-Length'])
            for value in ['bytes=16-', 'bytes=7-3', 'bytes=-0', 'bytes=-', 'bytes=0-1,3-4', 'items=0-1']:
                self.assertEqual(self.request(server, '/video.mp4', headers={'Range': value})[0], 416)
            self.assertEqual(self.request(server, '/empty.txt')[1]['Content-Length'], '0')
            self.assertEqual(self.request(server, '/empty.txt', headers={'Range': 'bytes=0-'})[0], 416)

    def test_local_package_rewrite_and_representation_hash(self):
        original = (self.dist / 'downloads.html').read_bytes()
        with self.running(packages=True) as server:
            status, headers, body = self.request(server, '/downloads.html')
            self.assertIn(b'/classroom-downloads/workshop-offline.zip', body)
            self.assertNotIn(b'https://github.com', body)
            self.assertEqual(headers['Content-Length'], str(len(body)))
            self.assertEqual(headers['ETag'], '"' + hashlib.sha256(body).hexdigest() + '"')
            head = self.request(server, '/downloads.html', 'HEAD')
            self.assertEqual(head[1]['Content-Length'], str(len(body)))
            self.assertEqual(head[2], b'')
            part = self.request(server, '/downloads.html', headers={'Range': 'bytes=0-7'})
            self.assertEqual(part[2], body[:8])
            for name in server_module.PACKAGE_NAMES:
                res = self.request(server, '/classroom-downloads/' + name)
                self.assertEqual(res[2], (self.root / name).read_bytes())
                self.assertIn(name, res[1]['Content-Disposition'])
        self.assertEqual((self.dist / 'downloads.html').read_bytes(), original)

    def test_manifest_hash_and_symlink_rejection(self):
        (self.dist / 'video.mp4').write_bytes(b'CHANGED')
        with self.assertRaises(ValueError):
            server_module.Catalogue(self.dist)
        (self.dist / 'video.mp4').unlink()
        (self.dist / 'video.mp4').symlink_to(self.root / 'outside.txt')
        with self.assertRaises(OSError):
            server_module.Catalogue(self.dist)

    def test_changed_and_symlink_swapped_assets_held(self):
        with self.running() as server:
            (self.dist / 'video.mp4').write_bytes(b'CHANGED')
            self.assertEqual(self.request(server, '/video.mp4')[0], 503)
            (self.dist / 'index.html').unlink()
            (self.dist / 'index.html').symlink_to(self.root / 'outside.txt')
            status, _, body = self.request(server)
            self.assertEqual(status, 503)
            self.assertNotIn(b'PRIVATE', body)
            (self.dist / 'nested/한글.txt').unlink()
            (self.dist / 'nested').rmdir()
            (self.dist / 'nested').symlink_to(self.root)
            self.assertEqual(self.request(server, '/nested/%ED%95%9C%EA%B8%80.txt')[0], 503)

    def test_unreviewed_packages_fail_start(self):
        (self.root / 'workshop-source.zip').write_bytes(b'bad')
        with self.assertRaises(ValueError):
            server_module.Catalogue(self.dist, self.root)

    def test_connection_limit(self):
        with self.running(connections=1) as server:
            held = socket.create_connection(('127.0.0.1', server.server_port), timeout=2)
            # The request thread is intentionally waiting for headers.
            deadline = time.monotonic() + 2
            while server.limits._value != 0 and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(server.limits._value, 0)
            overloaded = self.request(server)
            self.assertEqual(overloaded[0], 503)
            self.assertEqual(overloaded[1]['X-Classroom-Origin'], 'static-v1')
            held.close()
            deadline = time.monotonic() + 2
            while server.limits._value != 1 and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(self.request(server)[0], 200)

    def test_finite_expiry(self):
        catalogue = server_module.Catalogue(self.dist)
        server = server_module.ClassroomServer(('127.0.0.1', 0), catalogue)
        thread = threading.Thread(target=server.serve_for, args=(.2,))
        thread.start()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(server.socket.fileno(), -1)

    def test_cli_rejects_unbounded_hours(self):
        for hours in ['0', '-1', '169', 'nan', 'inf']:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                server_module.main(['--hours', hours])


if __name__ == '__main__':
    unittest.main()
