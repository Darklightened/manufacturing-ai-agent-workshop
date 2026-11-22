#!/usr/bin/env python3
"""Import a licensed source_pack ZIP after SHA256 and safe-path checks."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,io,stat,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--url',required=True);parser.add_argument('--sha256',required=True)
 args=parser.parse_args()
 if not args.url.startswith('https://'):raise ValueError('HTTPS media URL required')
 with urllib.request.urlopen(args.url,timeout=120) as r:
  blob=r.read(700*1024*1024+1)
 if len(blob)>700*1024*1024:raise ValueError('archive too large')
 if hashlib.sha256(blob).hexdigest()!=args.sha256.lower():raise ValueError('media checksum mismatch')
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  if sum(i.file_size for i in z.infolist())>900*1024*1024:raise ValueError('expanded archive too large')
  for info in z.infolist():
   p=PurePosixPath(info.filename)
   if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!='source_pack':raise ValueError('unsafe archive path')
   if '\\' in info.filename or stat.S_ISLNK(info.external_attr>>16):raise ValueError('unsafe archive entry')
  for info in z.infolist():
   dest=ROOT/'data'/info.filename
   dest.resolve().relative_to((ROOT/'data/source_pack').absolute())
   if info.is_dir():dest.mkdir(parents=True,exist_ok=True)
   else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(info))
 print('Media imported and archive SHA256 verified.')
if __name__=='__main__':main()
