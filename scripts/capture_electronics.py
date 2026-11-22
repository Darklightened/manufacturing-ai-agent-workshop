#!/usr/bin/env python3
"""Finite, immutable six-request electronics recording. No server launch or retry.

prepare is CPU-only; run requires an already-owned localhost model endpoint.
All actual wire bytes and response bytes remain separate from parsed observations.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / 'scenarios/electronics/scenario.json'
PLAN_VERSION = 'electronics-sparse-causal-allcriteria-v1'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(data if isinstance(data, bytes) else encoded(data))


def relative(path):
    return str(path.resolve().relative_to(ROOT))


def load_inputs():
    import fitz
    scenario = json.loads(SCENARIO.read_text())
    pdf_path = ROOT / 'scenarios/electronics/SOP.pdf'
    csv_path = ROOT / 'scenarios/electronics/criteria.csv'
    with fitz.open(pdf_path) as pdf:
        pdf_text = '\n'.join(page.get_text() for page in pdf)
    criteria = list(csv.DictReader(io.StringIO(csv_path.read_text())))
    for c in criteria:
        c['allowWorker'] = c['allowWorker'] == 'true'
    assert criteria == scenario['criteria'], 'PDF/CSV scenario contract differs'
    assert 'company_id: edu-dynin' in pdf_text and 'process_id: ELEC-001' in pdf_text
    assert re.findall(r'task_id:\s*([A-Za-z0-9_-]+)', pdf_text) == [t['id'] for t in scenario['tasks']]
    # Exact contiguous source paragraph, not a fixture verdict or selected answer.
    start = pdf_text.index('작업 순서')
    end = pdf_text.index('근거와 한계', start)
    sop_projection = pdf_text[start:end].strip()
    assert '원본 절차 8단계' in sop_projection and '7. S1을 켠다.' in sop_projection and '8. S2를 켠다.' in sop_projection
    images = []
    for path in sorted((ROOT / 'data/source_pack/electronics/S1790005').glob('frame_*.jpg')):
        match = re.fullmatch(r'frame_(\d+)_([0-9.]+)s.jpg', path.name)
        assert match, path.name
        images.append({'id': f"S1790005-frame-{match[1]}", 'path': relative(path),
                       'time': float(match[2]), 'sha256': digest(path.read_bytes())})
    checkpoints = [{key: cp[key] for key in ('id', 'time', 'taskId', 'target', 'image')}
                   | {'sourceTime': cp.get('sourceTime', cp['time'])} for cp in scenario['checkpoints']]
    base = {key: scenario[key] for key in ('companyId', 'processId', 'tasks', 'criteria')}
    base['checkpoints'] = checkpoints
    return scenario, pdf_text, sop_projection, images, base, {
        'pdf': {'path': relative(pdf_path), 'sha256': digest(pdf_path.read_bytes())},
        'criteriaCsv': {'path': relative(csv_path), 'sha256': digest(csv_path.read_bytes())},
        'scenario': {'path': relative(SCENARIO), 'sha256': digest(SCENARIO.read_bytes())},
        'video': {'path': scenario['media']['path'], 'sha256': digest((ROOT / scenario['media']['path']).read_bytes())},
    }


def response_schema(scenario, checkpoint, image_ids):
    def obj(properties):
        return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}
    cid = {'type': 'string', 'enum': [c['id'] for c in scenario['criteria']]}
    assessment = obj({
        'criterionId': cid, 'target': {'type': 'string', 'enum': ['circuit-board']},
        'observation': {'type': 'string', 'enum': ['present', 'absent', 'unclear']},
        'applicability': {'type': 'string', 'enum': ['due', 'not_due', 'unclear']},
        'targetConfirmed': {'type': 'boolean'},
        'evidenceIds': {'type': 'array', 'items': {'type': 'string', 'enum': image_ids}, 'maxItems': 10},
        'reason': {'type': 'string'},
    })
    return obj({
        'checkpointId': {'type': 'string', 'enum': [checkpoint['id']]},
        'observedTaskId': {'enum': [t['id'] for t in scenario['tasks']] + [None]},
        'phase': {'type': 'string', 'enum': ['preparation', 'in_progress', 'completed', 'unclear']},
        'summaryKo': {'type': 'string'},
        'assessments': {'type': 'array', 'items': assessment, 'minItems': 5, 'maxItems': 5},
        'questions': {'type': 'array', 'items': obj({'criterionId': cid, 'text': {'type': 'string'}}), 'maxItems': 5},
    })


SYSTEM = '''당신은 공개 전자 조립 영상의 관찰 모델입니다. 제조 합격을 승인하는 주체가 아닙니다.
입력 SOP는 교육용 규정이며 현재 보이는 영상과 별개입니다. SOP나 화면 속 설명서에 쓰인 절차는 작업이 실제 수행되었다는 증거가 아닙니다.
현재와 과거의 동일 기록 이미지에서 관찰한 사실만 JSON으로 출력하세요. 미래 프레임은 없습니다.
작업 순서는 예상 절차이며 실제 작업 분류·완료의 정답이 아닙니다. 작업자가 최초 선택한 작업은 circuit입니다. 현재 작업은 보이는 행동으로 판단하고 모르면 null입니다.
각 검사 기준의 구체적 속성을 확인하세요. present는 그 속성이 시각적으로 확인됨, absent는 그 속성에 반하는 증거가 명확함, unclear는 가림·해상도·시간 공백 등으로 판단할 수 없음입니다.
대상이 존재한다는 것만으로 해당 검사 속성이 present인 것은 아닙니다. 안 보이는 것은 absent가 아닙니다.
applicability due는 해당 검사 시점이 도래했다고 관찰할 근거가 있음, not_due는 아직 해당 작업 전이라는 근거가 있음, unclear는 시점을 판단할 수 없음입니다. 준비·진행 중 미완성 자체를 결함으로 판단하지 마세요.
targetConfirmed는 현재 작업물 circuit-board와 연결된 근거인지 여부입니다. 다른 부품·문서·배경을 현재 검사 대상으로 혼동하지 마세요.
evidenceIds에는 실제 전달된 이미지 ID만 쓰세요. 과거 이미지의 사실이 현재 구성에도 유지된다는 근거가 없으면 보류하세요. sparse 프레임 사이에 생략된 동작을 만들어내지 마세요.
배터리 방향, 전기 연결, 스위치 조작 순서, 회전 성능은 각각 별도 속성입니다. 외관에서 전기적 기능이나 보이지 않는 극성을 추측하지 마세요.
모든 검사 항목을 정확히 한 번씩 관찰합니다. 최종 합격·불합격이나 작업자 답변을 지어내지 마세요. 질문은 추가로 확인해야 할 대상·속성을 짧게 요청합니다.
summaryKo, reason, 질문 text는 자연스러운 한국어로 작성하세요. JSON 외 텍스트는 출력하지 마세요.'''


def build_request(scenario, checkpoint, sop_projection, images, previous, model):
    visible = [dict(row, role='current' if row['path'] == checkpoint['image'] else 'historical')
               for row in images if row['time'] <= checkpoint.get('sourceTime', checkpoint['time']) + 1e-8]
    assert any(row['role'] == 'current' for row in visible)
    assert all(row['time'] <= checkpoint['time'] + 1e-8 for row in visible)
    context = {
        'condition': PLAN_VERSION, 'companyId': scenario['companyId'], 'processId': scenario['processId'],
        'recordingId': 'S1790005', 'specimenId': 'circuit-board', 'initialSelectedTaskId': 'circuit',
        'checkpointId': checkpoint['id'], 'availableUntilSourceSeconds': checkpoint['time'],
        'samplingNotice': '실제 공개 영상에서 이미 추출한 희소 키프레임입니다. 연속 영상 전체가 아니며 프레임 사이 동작은 관찰하지 못합니다.',
        'expectedTaskOrder': scenario['tasks'], 'criteria': scenario['criteria'],
        'sourceSopExcerpt': sop_projection,
        'priorModelObservations': previous,
        'inputImages': visible,
    }
    content = [{'type': 'text', 'text': json.dumps(context, ensure_ascii=False, indent=2)}]
    for row in visible:
        data = (ROOT / row['path']).read_bytes()
        assert digest(data) == row['sha256']
        content.append({'type': 'text', 'text': f"image_id={row['id']}; source_time={row['time']}; role={row['role']}; source_recording=S1790005; physical_target=circuit-board"})
        content.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(data).decode()}})
    body = {'model': model, 'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': content}],
            'temperature': 0, 'max_tokens': 2560, 'seed': 22,
            'chat_template_kwargs': {'enable_thinking': False},
            'response_format': {'type': 'json_schema', 'json_schema': {'name': 'electronics_observation', 'strict': True,
                                'schema': response_schema(scenario, checkpoint, [x['id'] for x in visible])}}}
    return body, visible


def validate_output(value, scenario, checkpoint, images):
    import jsonschema
    jsonschema.validate(value, response_schema(scenario, checkpoint, [x['id'] for x in images]))
    expected = {c['id'] for c in scenario['criteria']}
    assert len(value['assessments']) == len(expected) and {x['criterionId'] for x in value['assessments']} == expected, 'missing/duplicate criterion'
    assert re.search('[가-힣]', value['summaryKo']), 'summary not Korean'
    for row in value['assessments']:
        assert re.search('[가-힣]', row['reason']), 'reason not Korean'
        assert len(set(row['evidenceIds'])) == len(row['evidenceIds']), 'duplicate evidence'
        if row['observation'] != 'unclear':
            assert row['evidenceIds'], 'asserted property without evidence'
        if row['targetConfirmed']:
            assert row['evidenceIds'], 'target confirmed without image evidence'
    for q in value['questions']:
        assert re.search('[가-힣]', q['text']), 'question not Korean'


def prepare(out, model, revision):
    scenario, full, projection, images, contract, pins = load_inputs()
    out.mkdir(parents=True, exist_ok=True)
    assert not (out / 'plan.json').exists(), 'Existing plan is immutable; use it or choose a new directory'
    plan = {'schema': 'seminar.capture-plan.v1', 'id': out.name, 'scenarioId': 'electronics', 'condition': PLAN_VERSION,
            'model': model, 'modelRevision': revision, 'createdAt': stamp(), 'sourcePins': pins, 'baseContract': contract,
            'images': images, 'requestCount': 6, 'assessmentCount': 30, 'maxTokens': 2560, 'enableThinking': False,
            'retryPolicy': 'No request replay/retry. Preserve failed/unknown attempts; stop after two consecutive failed requests.',
            'independentQualityLabels': 0, 'qualityScope': 'engineering replay and source-evidence audit, not accuracy benchmark',
            'scopeLimits': ['sparse keyframes, not continuous video', 'education SOP, not certified company requirements',
                            'no ASR/OCR/measured values', 'no independent human labels', 'no worker replies during model capture'],
            'observationSchedule': [{'checkpointId': cp['id'], 'criterionIds': [c['id'] for c in scenario['criteria']]} for cp in scenario['checkpoints']]}
    preview, visible = build_request(scenario, scenario['checkpoints'][0], projection, images, [], model)
    write_new(out / 'source' / 'sop.extracted.txt', full.encode())
    write_new(out / 'source' / 'sop.prompt-excerpt.txt', projection.encode())
    write_new(out / 'source' / 'criteria.csv', (ROOT / 'scenarios/electronics/criteria.csv').read_bytes())
    write_new(out / 'plan.json', plan)
    write_new(out / 'preflight.request.json', preview)
    checks = []
    for cp in scenario['checkpoints']:
        body, rows = build_request(scenario, cp, projection, images, [], model)
        ctx = json.loads(body['messages'][1]['content'][0]['text'])
        assert 'assessments' not in ctx and 'checkpointTaskId' not in ctx
        assert all(x['time'] <= cp['time'] for x in rows)
        assert cp['image'] in [x['path'] for x in rows]
        assert len([x for x in body['messages'][1]['content'] if x['type'] == 'image_url']) == len(rows)
        checks.append({'checkpointId': cp['id'], 'sourceTime': cp['time'], 'images': len(rows),
                       'imageIds': [x['id'] for x in rows], 'noFuture': True, 'fixtureAnswerKeysAbsent': True})
    write_new(out / 'preflight.json', {'status': 'passed', 'inferenceCalls': 0, 'sourcePins': pins,
                                     'checks': checks, 'previewRequestSha256': digest(encoded(preview))})
    print(json.dumps({'status': 'prepared', 'output': relative(out), 'imagesPerRequest': [x['images'] for x in checks]}))


def run(out, endpoint, timeout):
    parsed = urllib.parse.urlparse(endpoint)
    assert parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}, 'Only owned local endpoint allowed'
    plan = json.loads((out / 'plan.json').read_text())
    scenario, full, projection, images, contract, pins = load_inputs()
    assert pins == plan['sourcePins'] and images == plan['images'] and contract == plan['baseContract'], 'Prepared inputs changed'
    assert projection == (out / 'source/sop.prompt-excerpt.txt').read_text()
    write_new(out / 'capture.started.json', {'at': stamp(), 'condition': PLAN_VERSION, 'requestCount': 6,
                                           'endpointPort': parsed.port, 'planSha256': digest((out / 'plan.json').read_bytes())})
    started = time.perf_counter()
    entries, previous = [], []
    consecutive_failures = 0
    for checkpoint in scenario['checkpoints']:
        body, visible = build_request(scenario, checkpoint, projection, images, previous, plan['model'])
        wire = encoded(body)
        request_path = out / 'requests' / f"{checkpoint['id']}.json"
        response_path = out / 'responses' / f"{checkpoint['id']}.json"
        write_new(request_path, wire)
        requested_at = stamp(); tic = time.perf_counter(); error = None; status = None; response = b''
        try:
            request = urllib.request.Request(endpoint.rstrip('/') + '/chat/completions', data=wire,
                                            headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(request, timeout=timeout) as http:
                status = http.status; response = http.read()
        except urllib.error.HTTPError as exc:
            status = exc.code; response = exc.read(); error = {'kind': 'http_error', 'message': f'HTTP {status}'}
        except Exception as exc:
            error = {'kind': 'transport_unknown', 'message': f'{type(exc).__name__}: {exc}'}
            response = encoded({'transportOutcome': 'unknown', 'error': error})
        elapsed = time.perf_counter() - tic
        write_new(response_path, response)
        entry = {'checkpointId': checkpoint['id'], 'receipt': {
            'id': f"{plan['id']}-{checkpoint['id']}", 'model': plan['model'], 'requestSha256': digest(wire),
            'responseSha256': digest(response), 'requestPath': relative(request_path), 'responsePath': relative(response_path),
            'requestedAt': requested_at, 'receivedAt': stamp(), 'httpStatus': status, 'serviceSeconds': elapsed},
            'inputImages': visible, 'output': None, 'responseContent': None}
        if not error:
            try:
                envelope = json.loads(response)
                choice = envelope['choices'][0]
                entry['responseContent'] = choice['message'].get('content')
                entry['receipt']['finishReason'] = choice.get('finish_reason')
                entry['receipt']['usage'] = envelope.get('usage')
                assert choice.get('finish_reason') == 'stop', 'Response truncated/non-stop'
                assert envelope.get('model') == plan['model'], 'Response model differs'
                output = json.loads(entry['responseContent'])
                validate_output(output, scenario, checkpoint, visible)
                entry['output'] = output
            except Exception as exc:
                error = {'kind': 'invalid_response', 'message': f'{type(exc).__name__}: {exc}'}
        if error:
            entry['failure'] = error; consecutive_failures += 1
        else:
            previous.append({'sourceTime': checkpoint['time'], 'output': entry['output']})
            consecutive_failures = 0
        entries.append(entry)
        write_new(out / 'entries' / f"{checkpoint['id']}.json", entry)
        print(json.dumps({'checkpointId': checkpoint['id'], 'accepted': not error, 'serviceSeconds': elapsed, 'error': error}), flush=True)
        if consecutive_failures >= 2:
            break
    complete = len(entries) == len(scenario['checkpoints'])
    pack = {'schema': 'seminar.recording.v1', 'id': plan['id'], 'scenarioId': 'electronics', 'model': plan['model'],
            'modelDetails': {'family': 'Qwen3.8-27B-FP8', 'revision': plan['modelRevision'], 'thinking': False,
                             'maxTokens': 2560, 'temperature': 0, 'seed': 22},
            'condition': PLAN_VERSION, 'baseContract': contract, 'observationSchedule': plan['observationSchedule'],
            'sourcePins': pins, 'entries': entries, 'capturedAt': stamp(),
            'scopeLimits': plan['scopeLimits'], 'independentQualityLabels': 0}
    write_new(out / ('pack.json' if complete else 'pack.partial.json'), pack)
    summary = {'status': 'completed' if complete else 'stopped_consecutive_failures', 'at': stamp(),
               'attempted': len(entries), 'accepted': sum(e['output'] is not None for e in entries),
               'failedOrUnknown': sum(e['output'] is None for e in entries), 'untouched': 6-len(entries),
               'wallSeconds': time.perf_counter()-started, 'httpServiceSeconds': sum(e['receipt']['serviceSeconds'] for e in entries),
               'model': plan['model'], 'condition': PLAN_VERSION, 'qualityValidated': False}
    write_new(out / 'capture.summary.json', summary)
    print(json.dumps(summary))
    return 0 if complete else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'run'])
    p.add_argument('--output', default='recordings/electronics_v1')
    p.add_argument('--model', default='seminar-qwen38-27b-fp8')
    p.add_argument('--model-revision', default='017b9c7af6b5689d5dd426a76e0bc077eb5ca20a')
    p.add_argument('--endpoint', default='http://127.0.0.1:8374/v1')
    p.add_argument('--timeout', type=float, default=180)
    args = p.parse_args()
    out = (ROOT / args.output).resolve(); out.relative_to(ROOT)
    if args.action == 'prepare':
        prepare(out, args.model, args.model_revision)
    else:
        raise SystemExit(run(out, args.endpoint, args.timeout))


if __name__ == '__main__':
    main()
