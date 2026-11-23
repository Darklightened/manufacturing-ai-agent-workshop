#!/usr/bin/env python3
"""CPU-only browser derivative of the already-reviewed public teaching video.

Usage: python scripts/prepare_worker_media.py --ffmpeg /path/to/ffmpeg
The original source remains immutable. No cuts, speed changes or GPU acceleration.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/source_pack/electronics/S1790005/S1790005.mp4'
OUT = ROOT / 'assets/worker-flow'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def exact_mp4_times(path):
    raw=path.read_bytes(); result={}
    def walk(start,end):
        pos=start
        while pos+8<=end:
            size,kind=struct.unpack('>I4s',raw[pos:pos+8]);header=8
            if size==1:size=struct.unpack('>Q',raw[pos+8:pos+16])[0];header=16
            if size==0:size=end-pos
            if kind in (b'mvhd',b'mdhd'):
                cursor=pos+header
                if raw[cursor]==0:scale,ticks=struct.unpack('>II',raw[cursor+12:cursor+20])
                else:scale=struct.unpack('>I',raw[cursor+20:cursor+24])[0];ticks=struct.unpack('>Q',raw[cursor+24:cursor+32])[0]
                result[kind.decode()]={'timescale':scale,'ticks':ticks,'durationSeconds':ticks/scale}
            if kind in (b'moov',b'trak',b'mdia'):walk(pos+header,pos+size)
            pos+=size
    walk(0,len(raw))
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ffmpeg',default='ffmpeg');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    source_hash=digest(SOURCE)
    output=OUT/'assembly.webm'
    if output.exists():raise SystemExit('Refusing to replace an existing video; use a new output revision for another encode.')
    command=[args.ffmpeg,'-hide_banner','-nostdin','-i',str(SOURCE),'-map','0:v:0','-an','-vf','scale=640:360,fps=24','-c:v','libvpx-vp9','-b:v','650k','-crf','34','-row-mt','1','-cpu-used','4','-threads','4','-pix_fmt','yuv420p','-deadline','good',str(output)]
    subprocess.run(command,check=True)
    # Decode the entire derivative, not just its header, and collect final output time.
    check=subprocess.run([args.ffmpeg,'-hide_banner','-nostdin','-v','error','-i',str(output),'-map','0:v:0','-f','null','-','-progress','pipe:1'],capture_output=True,text=True,check=True)
    if check.stderr.strip():raise RuntimeError(check.stderr)
    clocks=re.findall(r'^out_time_us=(\d+)$',check.stdout,re.M)
    if not clocks:raise RuntimeError('No decode duration reported')
    duration=int(clocks[-1])/1_000_000
    times=exact_mp4_times(SOURCE)
    if abs(duration-times['mdhd']['durationSeconds'])>1/24+0.002:raise RuntimeError('Derived timebase differs by more than one encoded frame')
    if digest(SOURCE)!=source_hash:raise RuntimeError('Original bytes changed')
    if output.stat().st_size>=15*1024*1024:raise RuntimeError('Video exceeds teaching download size budget')
    metadata={
      'schema':'seminar.worker-media.v1',
      'media':{'path':'assets/worker-flow/assembly.webm','codec':'vp9','container':'webm','width':640,'height':360,'fps':24,'durationSeconds':duration,'bytes':output.stat().st_size,'sha256':digest(output),'audio':False},
      'source':{'path':str(SOURCE.relative_to(ROOT)),'dataset':'EgoOops','videoId':'S1790005','codec':'h264','width':1280,'height':720,'fpsNumerator':30000,'fpsDenominator':1001,'durationSeconds':times['mvhd']['durationSeconds'],'videoDurationSeconds':times['mdhd']['durationSeconds'],'bytes':SOURCE.stat().st_size,'sha256':source_hash,'url':'https://y-haneji.github.io/EgoOops-project-page/','attribution':'EgoOops · Yuto Haneji et al.','license':'CC BY-SA 4.0','licenseUrl':'https://creativecommons.org/licenses/by-sa/4.0/'},
      'transformation':{'cuts':False,'speedFactor':1,'sourceTimeOffsetSeconds':0,'method':'CPU ffmpeg libvpx-vp9; scale=640:360,fps=24; no audio in source; no generated frames or overlays','durationToleranceSeconds':1/24,'note':'End duration may differ by up to one encoded frame because of 24 fps rounding.'},
      'authoredTeachingNotice':'작업 경계·검사 항목·질문은 강의용으로 작성한 예시이며 원본 데이터셋의 정답 주석이나 실제 모델 출력이 아닙니다.',
      'checks':{'originalHashPreserved':True,'fullCpuDecodePassed':True,'decodeErrors':[],'gpuUsed':False,'modelCalls':0},
      'avatar':{'path':'assets/worker-flow/avatar.svg','provenance':'original code-drawn neutral silhouette for classroom use; no real person or face recognition','license':'CC0-1.0'}
    }
    (OUT/'media.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(metadata,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
