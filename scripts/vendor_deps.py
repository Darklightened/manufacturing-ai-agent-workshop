#!/usr/bin/env python3
"""Fetch only pinned, integrity-checked browser dependencies. No npm install."""
from pathlib import Path
import base64, hashlib, io, json, tarfile, urllib.request
ROOT=Path(__file__).resolve().parents[1]
PACKAGES=[
 ('pdfjs-dist','4.10.38','sha512-/Y3fcFrXEAsMjJXeL9J8+ZG9U01LbuWaYypvDW2ycW1jL269L3js3DVBjDJ0Up9Np1uqDXsDrRihHANhZOlwdQ==',{'package/build/pdf.mjs':'pdfjs/pdf.mjs','package/build/pdf.worker.mjs':'pdfjs/pdf.worker.mjs','package/LICENSE':'pdfjs/LICENSE'}),
 ('sql.js','1.11.0','sha512-GsLUDU3vhOo14Pd5ME0y2te49JQyby6HuoCuadevEV+CGgTUjmYRrm7B7lhRyzOgrmcWmspUfyjNb6sOAEqdsA==',{'package/dist/sql-wasm.js':'sqljs/sql-wasm.js','package/dist/sql-wasm.wasm':'sqljs/sql-wasm.wasm','package/LICENSE':'sqljs/LICENSE'})]
def main():
 records=[]
 for name,version,integrity,members in PACKAGES:
  url=f'https://registry.npmjs.org/{name}/-/{name}-{version}.tgz'
  with urllib.request.urlopen(url,timeout=60) as response: data=response.read()
  actual='sha512-'+base64.b64encode(hashlib.sha512(data).digest()).decode()
  if actual!=integrity: raise ValueError(f'integrity mismatch: {name}')
  with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
   for source,destination in members.items():
    member=archive.getmember(source)
    if not member.isfile():raise ValueError('dependency member is not regular file')
    blob=archive.extractfile(member).read();target=ROOT/'vendor'/destination
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(blob)
    records.append({'package':name,'version':version,'source':url,'integrity':integrity,'path':'vendor/'+destination,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
 (ROOT/'vendor/manifest.json').write_text(json.dumps({'schema':'seminar.vendor.v1','files':records},indent=2)+'\n')
 print(json.dumps({'files':len(records),'bytes':sum(x['bytes'] for x in records)}))
if __name__=='__main__':main()
