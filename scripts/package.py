#!/usr/bin/env python3
"""Create local source, media and offline ZIP candidates. Does not publish."""
from pathlib import Path
import argparse,hashlib,json,zipfile
from build import ROOT,safe_file
FIXED=['index.html','downloads.html','app.mjs','styles.css','README.md','README.ko.md','START_HERE.ko.md','DATA_LICENSES.md','package.json','.gitignore']
DIRS=['packages','scenarios','recordings','assets','vendor','docs','slides','scripts','tests','.github']
def write_zip(path,entries):
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
  for source,target in entries:
   safe_file(source);archive.write(source,target)
 with zipfile.ZipFile(path) as archive:
  bad=archive.testzip()
  if bad:raise ValueError(f'bad ZIP member: {bad}')
 return {'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'files':len(entries)}
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--windows',action='store_true',help='Also package the optional bundled-runtime Windows ZIP')
 parser.add_argument('--windows-only',action='store_true',help='Package only the optional Windows ZIP')
 parser.add_argument('--runtime-archive',type=Path,help='Locally cached official embeddable Python ZIP; SHA256 is verified')
 args=parser.parse_args()
 if not (ROOT/'dist/build-manifest.json').is_file():raise ValueError('run build.py first')
 if args.windows_only:
  from package_windows import package_windows
  record=package_windows(args.runtime_archive)
  (ROOT/'windows-package-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
  print(json.dumps(record));return
 source=[ROOT/rel for rel in FIXED]
 for rel in DIRS:
  folder=ROOT/rel
  if folder.exists():source += [p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and not any(x.startswith('.') for x in p.relative_to(folder).parts)]
 source=sorted(set(source))
 media=sorted(p for p in (ROOT/'dist/data/source_pack').rglob('*') if p.is_file())
 prefix='11_21_seminar/'
 source_entries=[(p,prefix+str(p.relative_to(ROOT))) for p in source]
 media_entries=[(p,str(p.relative_to(ROOT/'dist/data'))) for p in media]
 offline_entries=source_entries+[(p,prefix+str(p.relative_to(ROOT/'dist'))) for p in media]
 records=[]
 records.append(write_zip(ROOT/'workshop-source.zip',source_entries))
 records.append(write_zip(ROOT/'workshop-media.zip',media_entries))
 records.append(write_zip(ROOT/'workshop-offline.zip',offline_entries))
 # Small, student-facing pack: inputs and finished example forms, without video/code.
 handouts=[ROOT/'DATA_LICENSES.md',ROOT/'assets/fonts/OFL.txt',ROOT/'docs/TEACHING_DEMO.ko.md',ROOT/'docs/MEASUREMENT_DEMO.ko.md']
 for name in ['electronics_demo','measurement_demo','measurement_precision_demo','measurement_input_demo','measurement_input_precision_demo','mechanical_demo']:
  handouts += [p for p in (ROOT/'scenarios'/name).iterdir() if p.suffix in {'.pdf','.csv','.svg'}]
 handouts += list((ROOT/'docs/measurement_demo_v1/examples').glob('*.html'))
 handouts += list((ROOT/'docs/measurement_input_v2/examples').glob('*.html'))
 handouts += [p for p in (ROOT/'assets/mechanical-flow/examples').glob('*') if p.suffix in {'.html','.pdf'}]
 handouts += [ROOT/'docs/MECHANICAL_DEMO.ko.md']
 handouts += [ROOT/'docs/worker_monitor_v3/README.ko.md']
 handouts += [p for p in (ROOT/'assets/worker-flow/examples').glob('*') if p.suffix in {'.docx','.html','.pdf'}]
 records.append(write_zip(ROOT/'workshop-handouts.zip',[(p,'workshop-handouts/'+str(p.relative_to(ROOT))) for p in sorted(set(handouts))]))
 if args.windows:
  from package_windows import package_windows
  record=package_windows(args.runtime_archive);records.append(record)
  (ROOT/'windows-package-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
 build=json.loads((ROOT/'dist/build-manifest.json').read_text())
 result={'schema':'seminar.packages.v3','published':False,'default_scenario':build.get('default_scenario'),'teaching_scenarios':build.get('teaching_scenarios',[]),'modes':build['modes'],'playback_inference_calls':0,'recordings':build['recordings'],'packages':records}
 (ROOT/'packages-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()
