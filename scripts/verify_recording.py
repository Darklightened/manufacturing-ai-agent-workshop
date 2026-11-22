"""Read-only independent wire/provenance audit of a saved workshop recording."""
import argparse, base64, hashlib, json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def audit(pack_path):
    pack=json.loads(pack_path.read_text());previous=[];rows=[];counts=Counter();service=[]
    for pin in pack['sourcePins'].values():
        assert sha((ROOT/pin['path']).read_bytes())==pin['sha256'],pin['path']
    for entry in pack['entries']:
        receipt=entry['receipt'];req_raw=(ROOT/receipt['requestPath']).read_bytes();res_raw=(ROOT/receipt['responsePath']).read_bytes()
        assert sha(req_raw)==receipt['requestSha256']
        assert sha(res_raw)==receipt['responseSha256']
        req=json.loads(req_raw);parts=req['messages'][1]['content'];context=json.loads(parts[0]['text'])
        assert req['model']==pack['model'] and req['max_tokens']==pack['modelDetails']['maxTokens']
        assert req['chat_template_kwargs']['enable_thinking'] is False
        assert context['checkpointId']==entry['checkpointId']
        assert context['criteria']==pack['baseContract']['criteria']
        assert context['expectedTaskOrder']==pack['baseContract']['tasks']
        assert context['priorModelObservations']==previous
        assert context['inputImages']==entry['inputImages']
        assert 'checkpointTaskId' not in context and 'assessments' not in context
        pixels=[x['image_url']['url'] for x in parts if x['type']=='image_url']
        assert len(pixels)==len(entry['inputImages'])
        for url,im in zip(pixels,entry['inputImages']):
            assert url.startswith('data:image/jpeg;base64,')
            assert sha(base64.b64decode(url.split(',',1)[1],validate=True))==im['sha256']
            assert sha((ROOT/im['path']).read_bytes())==im['sha256']
            assert im['time']<=context['availableUntilSourceSeconds']
        row={'checkpointId':entry['checkpointId'],'sourceTime':context['availableUntilSourceSeconds'],'images':len(pixels),'accepted':entry['output'] is not None,'serviceSeconds':receipt['serviceSeconds']}
        if entry['output'] is not None:
            response=json.loads(res_raw);choice=response['choices'][0]
            assert response['model']==pack['model'] and choice['finish_reason']=='stop'
            assert choice['message']['content']==entry['responseContent']
            assert json.loads(choice['message']['content'])==entry['output']
            output=entry['output'];assert len(output['assessments'])==5
            counts.update(f"{x['observation']}/{x['applicability']}" for x in output['assessments'])
            previous.append({'sourceTime':context['availableUntilSourceSeconds'],'output':output})
            row.update(observedTaskId=output['observedTaskId'],phase=output['phase'],usage=receipt['usage'])
        rows.append(row);service.append(receipt['serviceSeconds'])
    return {'status':'passed','recording':pack['id'],'model':pack['model'],'requests':len(rows),'accepted':sum(x['accepted'] for x in rows),'observations':sum(counts.values()),'observationApplicabilityCounts':dict(counts),'httpServiceSeconds':sum(service),'noFuturePixels':True,'exactWirePixels':True,'causalPriorOutputs':True,'originalResponsesUnchanged':True,'independentAccuracyEstablished':False,'checkpoints':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pack',default='recordings/electronics_v1/pack.json');p.add_argument('--output');a=p.parse_args()
    result=audit(ROOT/a.pack)
    if a.output:
        dest=ROOT/a.output;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
