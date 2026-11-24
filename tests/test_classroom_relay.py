"""Loopback-only tests; no real host, SSH, firewall, GPU or classroom port."""
import importlib.util
import http.client
import http.server
from pathlib import Path
import threading
import unittest
import json,subprocess,sys,tempfile

spec=importlib.util.spec_from_file_location('classroom_relay',Path(__file__).resolve().parents[1]/'scripts/classroom_relay.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Origin(http.server.BaseHTTPRequestHandler):
    received=[]
    def log_message(self,*_):pass
    def do_HEAD(self):self.do_GET(True)
    def do_GET(self,head=False):
        self.received.append((self.command,self.path,dict(self.headers)))
        body=b'0123456789';status=200
        if self.headers.get('Range')=='bytes=2-5':body=b'2345';status=206
        self.send_response(status)
        if self.path!='/assets/unknown-service':self.send_header('X-Classroom-Origin','static-v1')
        self.send_header('Content-Type','application/octet-stream')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Accept-Ranges','bytes')
        if status==206:self.send_header('Content-Range','bytes 2-5/10')
        self.send_header('Set-Cookie','never=forwarded')
        self.end_headers()
        if not head:self.wfile.write(body)

class RelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.origin=http.server.ThreadingHTTPServer(('127.0.0.1',0),Origin)
        cls.relay=m.RelayServer(('127.0.0.1',0),cls.origin.server_port)
        cls.threads=[]
        for s in (cls.origin,cls.relay):
            t=threading.Thread(target=s.serve_forever,daemon=True);t.start();cls.threads.append(t)
    @classmethod
    def tearDownClass(cls):
        for s in (cls.relay,cls.origin):s.shutdown();s.server_close()
        for t in cls.threads:t.join(3)
    def request(self,method='GET',path='/',headers=None,body=None):
        c=http.client.HTTPConnection('127.0.0.1',self.relay.server_port,timeout=3);c.request(method,path,body=body,headers=headers or {})
        r=c.getresponse();out=(r.status,dict(r.getheaders()),r.read());c.close();return out
    def test_file_stream_and_private_headers(self):
        status,h,b=self.request(headers={'Authorization':'secret','Cookie':'private','Host':'evil.invalid'})
        self.assertEqual((status,b),(200,b'0123456789'));self.assertNotIn('Set-Cookie',h)
        got=Origin.received[-1][2];self.assertNotIn('Authorization',got);self.assertNotIn('Cookie',got);self.assertEqual(got['Host'],f'127.0.0.1:{self.origin.server_port}')
    def test_head_and_range(self):
        status,h,b=self.request('HEAD','/assets/video.mp4');self.assertEqual((status,b),(200,b''));self.assertEqual(h['Content-Length'],'10')
        status,h,b=self.request(path='/assets/video.mp4',headers={'Range':'bytes=2-5'});self.assertEqual((status,b),(206,b'2345'));self.assertEqual(h['Content-Range'],'bytes 2-5/10')
    def test_methods_and_body_rejected(self):
        before=len(Origin.received)
        for method in ['POST','PUT','DELETE','CONNECT','TRACE','OPTIONS','PATCH']:self.assertEqual(self.request(method)[0],405)
        self.assertEqual(self.request(body=b'upload')[0],400);self.assertEqual(before,len(Origin.received))
    def test_bad_paths_never_reach_origin(self):
        before=len(Origin.received)
        for p in ['/../secret','/%2e%2e/secret','/assets/.env','/assets/%252e%252e/file','/assets/a%5cb','/validation/receipt.json','/scripts/other.py','/assets/%00','http://elsewhere/private']:
            with self.subTest(path=p):self.assertEqual(self.request(path=p)[0],403)
        self.assertEqual(before,len(Origin.received))
    def test_unknown_origin_identity_fails_closed(self):self.assertEqual(self.request(path='/assets/unknown-service')[0],502)
    def test_multiple_range_rejected(self):self.assertEqual(self.request(headers={'Range':'bytes=0-1,3-4'})[0],400)
    def test_expired(self):
        old=self.relay.deadline;self.relay.deadline=0
        try:self.assertEqual(self.request()[0],503)
        finally:self.relay.deadline=old
    def test_bounds(self):
        for hours in [0,-1,169]:
            with self.assertRaises(ValueError):m.RelayServer(('127.0.0.1',0),lifetime_seconds=hours*3600)
    def test_connection_limit_fails_closed(self):
        for _ in range(32):self.assertTrue(self.relay.slots.acquire(blocking=False))
        before=len(Origin.received)
        try:self.assertEqual(self.request()[0],503)
        finally:
            for _ in range(32):self.relay.slots.release()
        self.assertEqual(before,len(Origin.received))
    def test_cli_exits_at_its_deadline(self):
        import socket
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'runtime.json'
            done=subprocess.run([sys.executable,str(Path(m.__file__)),'--host','127.0.0.1','--port',str(port),'--lifetime-hours','.00015','--state-file',str(state)],capture_output=True,text=True,timeout=6)
            self.assertEqual(done.returncode,0,done.stderr)
            self.assertEqual(json.loads(state.read_text())['status'],'stopped')
    def test_no_arbitrary_upstream(self):self.assertEqual(m.UPSTREAM_HOST,'127.0.0.1')

if __name__=='__main__':unittest.main()
