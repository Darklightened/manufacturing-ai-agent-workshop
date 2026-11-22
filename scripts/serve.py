#!/usr/bin/env python3
"""Local static server with single-byte-range video seeking. Default loopback only."""
import argparse,functools,http.server,mimetypes,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Handler(http.server.SimpleHTTPRequestHandler):
 def send_head(self):
  self._range=None
  path=Path(self.translate_path(self.path)); root=Path(self.directory).resolve()
  try:path.resolve().relative_to(root)
  except ValueError:
   self.send_error(403,'outside root');return None
  if not path.is_file():return super().send_head()
  size=path.stat().st_size
  range_header=self.headers.get('Range')
  if not range_header:return super().send_head()
  match=re.fullmatch(r'bytes=(\d*)-(\d*)',range_header.strip())
  if not match or size==0:return self.range_error(size)
  first,last=match.groups()
  if not first and not last:return self.range_error(size)
  if first:
   start=int(first);end=min(int(last),size-1) if last else size-1
  else:
   length=int(last)
   if not length:return self.range_error(size)
   start=max(0,size-length);end=size-1
  if start>end or start>=size:return self.range_error(size)
  stream=path.open('rb');stream.seek(start);self._range=(start,end)
  self.send_response(206)
  self.send_header('Content-Type',self.guess_type(str(path)))
  self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  self.send_header('Content-Length',str(end-start+1))
  self.send_header('Last-Modified',self.date_time_string(path.stat().st_mtime))
  self.end_headers();return stream
 def range_error(self,size):
  self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return None
 def copyfile(self,source,output):
  if not self._range:return super().copyfile(source,output)
  remaining=self._range[1]-self._range[0]+1
  while remaining:
   chunk=source.read(min(65536,remaining))
   if not chunk:break
   output.write(chunk);remaining-=len(chunk)
 def end_headers(self):
  self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-cache');self.send_header('X-Content-Type-Options','nosniff');super().end_headers()
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8921)
 parser.add_argument('--directory',type=Path,default=ROOT)
 args=parser.parse_args()
 mimetypes.add_type('application/wasm','.wasm');mimetypes.add_type('text/javascript','.mjs')
 handler=functools.partial(Handler,directory=str(args.directory.resolve()))
 server=http.server.ThreadingHTTPServer((args.host,args.port),handler)
 print(f'Workshop: http://{args.host}:{server.server_port}/',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
if __name__=='__main__':main()
