#!/usr/bin/env python3
"""CPU-only, camera-motion videos from authored static measurement images.

Not filmed smart-glass footage and not an AI/model measurement result. Source
PNGs remain unchanged. FFmpeg performs all image scaling and video encoding.
"""
import argparse, hashlib, json, re, subprocess, tempfile
from pathlib import Path
from datetime import datetime, timezone
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
ROOT=Path(__file__).resolve().parents[1]
LABELS={'a':'A · 외경 측정','b':'B · 전체 길이 측정','c':'C · 플랜지 두께 확인'}
DEFAULT_FFMPEG='/tmp/seminar_worker_media_tools/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(argv,log):
 r=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 log.write_text(r.stderr,encoding='utf-8')
 if r.returncode:raise RuntimeError(f'FFmpeg failed ({r.returncode}); see {log}')
 if 'failed to find any fallback with glyph' in r.stderr:raise RuntimeError(f'Missing subtitle glyphs; see {log}')
 return r

def subtitle(label):
 return f'''[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Header,Dynin Demo Korean,24,&H00FFFFFF,&H00FFFFFF,&H00101827,&H00101827,-1,0,0,0,100,100,0,0,1,0,0,7,40,40,18,1
Style: Scene,Dynin Demo Korean,21,&H00B9D4FF,&H00B9D4FF,&H00101827,&H00101827,-1,0,0,0,100,100,0,0,1,0,0,9,40,40,20,1
Style: Footer,Dynin Demo Korean,17,&H00DBE6F7,&H00DBE6F7,&H00101827,&H00101827,0,0,0,0,100,100,0,0,1,0,0,2,30,30,8,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:10.00,Header,,0,0,0,,스마트 글래스 시점 모의 영상
Dialogue: 0,0:00:00.00,0:00:10.00,Scene,,0,0,0,,{label}
Dialogue: 0,0:00:00.00,0:00:10.00,Footer,,0,0,0,,AI 생성 이미지 기반 · 강의용 예시 · 카메라 시점 이동만 적용
'''

def probe(ffmpeg,path,log):
 r=command([ffmpeg,'-hide_banner','-i',str(path),'-map','0:v:0','-f','null','-'],log)
 # Full decode checks the delivered files, not only the container header.
 text=r.stderr
 duration=re.search(r'Duration: (\d+):(\d+):([\d.]+)',text)
 seconds=int(duration[1])*3600+int(duration[2])*60+float(duration[3]) if duration else None
 frames=re.findall(r'frame=\s*(\d+)',text)
 codec=re.search(r'Video: ([^,\s]+)',text)
 stream=next(x for x in text.splitlines() if 'Video:' in x)
 dimensions=re.search(r'(\d{2,5})x(\d{2,5})',stream)
 fps_match=re.search(r'([\d.]+) fps',stream)
 assert dimensions and int(dimensions[1])==1280 and int(dimensions[2])==720,stream
 assert fps_match and float(fps_match[1])==24,stream
 assert seconds is not None and abs(seconds-(30 if path.stem=='overview' else 10))<.1,(path,seconds)
 return {'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':digest(path),'duration_seconds':seconds,'codec':codec[1] if codec else None,'decoded_frames':int(frames[-1]) if frames else None,'width':int(dimensions[1]),'height':int(dimensions[2]),'fps':float(fps_match[1]),'audio':False,'full_decode_exit':r.returncode}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ffmpeg',default=DEFAULT_FFMPEG);p.add_argument('--assets',type=Path,default=ROOT/'assets/measurement-photo-v1');p.add_argument('--scenes',nargs='+',choices=LABELS,default=list(LABELS));p.add_argument('--overview',action='store_true');p.add_argument('--validation',type=Path,required=True);a=p.parse_args();a.assets=a.assets.resolve();a.validation.mkdir(parents=True,exist_ok=True)
 sources={s:a.assets/f'scene-{s}.png' for s in a.scenes}
 for s,src in sources.items():
  if not src.is_file():raise FileNotFoundError(src)
 before={str(src):digest(src) for src in sources.values()}
 manifest_path=a.assets/'video-manifest.json';manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'version':1,'provenance':'authored_simulated_video','source_kind':'AI-generated static illustrations','actual_smart_glasses_capture':False,'model_prediction':False,'motion':'camera-only 1.000–1.030 zoom, slight bounded pan; no independently animated tools, hands, contact or display','frame_size':[1280,720],'fps':24,'scene_seconds':10,'audio':False,'sources':{},'outputs':{}}
 with tempfile.TemporaryDirectory(prefix='measurement-pov-') as td:
  t=Path(td)
  fonts=t/'fonts';fonts.mkdir()
  font=TTFont(ROOT/'assets/fonts/NotoSansKR.ttf')
  font=instantiateVariableFont(font,{'wght':500},inplace=False)
  for name in font['name'].names:
   if name.nameID in [1,4,6,16]:font['name'].setName('DyninDemoKorean' if name.nameID==6 else 'Dynin Demo Korean',name.nameID,name.platformID,name.platEncID,name.langID)
   elif name.nameID in [2,17]:font['name'].setName('Regular',name.nameID,name.platformID,name.platEncID,name.langID)
  font.save(fonts/'DyninDemoKorean.ttf')
  for scene,src in sources.items():
   ass=t/f'{scene}.ass';ass.write_text(subtitle(LABELS[scene]),encoding='utf-8')
   # Original aspect is retained in a 930×620 camera window with letterboxing.
   # All pixels move together. Tiny framing drift never simulates a tool operation.
   vf="zoompan=z='1.015+0.015*sin(2*PI*on/240-PI/2)':x='max(0,min(iw-iw/zoom,(iw-iw/zoom)/2+3*sin(on/44)))':y='max(0,min(ih-ih/zoom,(ih-ih/zoom)/2+2*sin(on/51)))':d=240:s=930x620:fps=24,pad=1280:720:175:64:color=0x101827,setsar=1,ass=filename="+str(ass)+":fontsdir="+str(fonts)+",format=yuv420p"
   mp4=a.assets/f'scene-{scene}.mp4'
   command([a.ffmpeg,'-hide_banner','-y','-threads','2','-i',str(src),'-vf',vf,'-t','10','-an','-c:v','libx264','-threads','2','-preset','medium','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(mp4)],a.validation/f'{scene}-mp4.log')
   webm=a.assets/f'scene-{scene}.webm'
   command([a.ffmpeg,'-hide_banner','-y','-i',str(mp4),'-an','-c:v','libvpx-vp9','-threads','2','-row-mt','1','-cpu-used','4','-b:v','0','-crf','27',str(webm)],a.validation/f'{scene}-webm.log')
   manifest['sources'][scene]={'path':str(src.relative_to(ROOT)),'sha256':before[str(src)],'label':LABELS[scene]}
   for f in [mp4,webm]:manifest['outputs'][f.name]=probe(a.ffmpeg,f,a.validation/f'{f.stem}-{f.suffix[1:]}-decode.log')
   manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(f'completed scene-{scene}',flush=True)
  if a.overview:
   for ext in ['mp4','webm']:
    clips=[a.assets/f'scene-{s}.{ext}' for s in LABELS]
    if not all(x.is_file() for x in clips):raise FileNotFoundError('All three scene videos required for overview')
    listing=t/f'concat-{ext}.txt';listing.write_text(''.join("file '"+str(x).replace("'","'\\''")+"'\n" for x in clips))
    dest=a.assets/f'overview.{ext}';args=[a.ffmpeg,'-hide_banner','-y','-f','concat','-safe','0','-i',str(listing),'-map','0:v:0','-c','copy']
    if ext=='mp4':args+=['-movflags','+faststart']
    command(args+[str(dest)],a.validation/f'overview-{ext}.log');manifest['outputs'][dest.name]=probe(a.ffmpeg,dest,a.validation/f'overview-{ext}-decode.log')
   print('completed overview',flush=True)
 for src,h in before.items():assert digest(Path(src))==h,'Source PNG changed'
 manifest['updated_at']=datetime.now(timezone.utc).isoformat();manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 receipt={'status':'passed','scope':'CPU generation and full decoder verification; browser/visual checks separate','scenes':a.scenes,'overview':a.overview,'source_pngs_unchanged':True,'provenance':manifest['provenance'],'outputs':manifest['outputs'],'model_calls':0,'gpu_calls':0}
 (a.validation/'VIDEO_BUILD.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
