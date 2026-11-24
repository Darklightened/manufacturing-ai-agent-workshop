#!/usr/bin/env python3
"""Build a static public candidate from an explicit source allowlist. Never deploy."""
from pathlib import Path
import hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
FIXED=['index.html','downloads.html','app.mjs','styles.css','README.md','README.ko.md','DATA_LICENSES.md','START_HERE.ko.md','scripts/serve.py']
DIRS=['packages','scenarios','recordings','assets','vendor','docs','slides']
ALLOWED_SOURCE_SUFFIXES={'.mp4','.jpg','.jpeg','.png','.pdf','.csv','.xlsx','.txt','.md'}
SENSITIVE_PATTERNS=[re.compile(r'/home/[A-Za-z0-9._-]+/[^\s"<>\\]+'),re.compile(r'(?i)(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,})')]
def safe_file(source):
 if source.is_symlink():raise ValueError(f'symlink not allowed: {source.relative_to(ROOT)}')
 source.resolve().relative_to(ROOT)
 if source.stat().st_size>99*1024*1024:raise ValueError(f'oversized public git candidate: {source.name}')
 if source.suffix in {'.md','.json','.js','.mjs','.html','.css','.txt','.csv'}:
  text=source.read_text(errors='replace')
  for pattern in SENSITIVE_PATTERNS:
   if pattern.search(text):raise ValueError(f'private path or credential pattern in {source.relative_to(ROOT)}')
def main():
 if OUT.exists():shutil.rmtree(OUT)
 OUT.mkdir();selected=[]
 for rel in FIXED:
  source=ROOT/rel
  if not source.is_file():raise FileNotFoundError(f'required app file: {source}')
  selected.append(source)
 for rel in DIRS:
  source=ROOT/rel
  if source.exists():selected += [p for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not any(x.startswith('.') for x in p.relative_to(source).parts)]
 # Media required by scenario JSON are exact local references, not arbitrary source files.
 source_pack=ROOT/'data/source_pack'
 referenced=set()
 configs=list((ROOT/'scenarios').rglob('*.json'))
 if (ROOT/'recordings').exists():configs+=list((ROOT/'recordings').rglob('*.json'))
 for config in configs:
  def walk(value):
   if isinstance(value,dict):
    for child in value.values():walk(child)
   elif isinstance(value,list):
    for child in value:walk(child)
   elif isinstance(value,str) and value.startswith('data/source_pack/'):
    referenced.add(value.split('#')[0])
  walk(json.loads(config.read_text()))
 for rel in referenced:
  source=ROOT/rel
  if not source.is_file():raise FileNotFoundError(f'scenario references missing source: {rel}')
  if source.suffix.lower() not in ALLOWED_SOURCE_SUFFIXES:raise ValueError(f'unapproved media type: {rel}')
  selected.append(source)
 # Preserve copyright/license notices, source facts and attribution without private archive metadata.
 if source_pack.exists():
  for source in source_pack.rglob('*'):
   if source.is_file() and ('license' in source.name.lower() ):
    selected.append(source)
 records=[]
 for source in sorted(set(selected)):
  safe_file(source);rel=source.relative_to(ROOT);dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
  records.append({'path':rel.as_posix(),'bytes':source.stat().st_size,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
 total=sum(x['bytes'] for x in records)
 if total>900*1024*1024:raise ValueError('static build exceeds configured size budget')
 (OUT/'.nojekyll').write_text('')
 packs=[]
 if (ROOT/'recordings').exists():
  for p in sorted((ROOT/'recordings').glob('*/pack.json')):
   pack=json.loads(p.read_text());packs.append({'id':pack['id'],'model':pack['model'],'entries':len(pack['entries']),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 demo=(ROOT/'scenarios/electronics_demo/scenario.json').is_file()
 teaching=[json.loads(p.read_text())['id'] for p in sorted((ROOT/'scenarios').glob('*/scenario.json')) if json.loads(p.read_text()).get('mode')=='demo']
 (OUT/'build-manifest.json').write_text(json.dumps({'schema':'seminar.build.v3','default_scenario':'electronics_demo' if demo else 'electronics','teaching_scenarios':teaching,'modes':(['authored_demo'] if demo else [])+['authored_fixture']+(['recorded_model'] if packs else []),'playback_inference_calls':0,'recordings':packs,'files':records,'bytes':total},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'files':len(records),'bytes':total,'output':str(OUT),'published':False}))
if __name__=='__main__':main()
