"""CPU admission tests for the actual capture builder; never calls a model."""
import base64
import copy
import hashlib
import json
import unittest

import capture_electronics as capture


class ActualWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario, cls.full, cls.projection, cls.images, cls.contract, cls.pins = capture.load_inputs()

    def request(self, index=0, previous=None):
        cp = self.scenario['checkpoints'][index]
        body, rows = capture.build_request(self.scenario, cp, self.projection, self.images, previous or [], 'test-model')
        return cp, body, rows

    def output(self):
        cp, _, rows = self.request()
        return cp, rows, {'checkpointId': cp['id'], 'observedTaskId': 'circuit', 'phase': 'in_progress', 'summaryKo': '회로 조립 중입니다.',
            'assessments': [{'criterionId': c['id'], 'target': c['target'], 'observation': 'unclear', 'applicability': 'unclear',
                            'targetConfirmed': True, 'evidenceIds': [rows[-1]['id']], 'reason': '확인할 수 없습니다.'} for c in self.scenario['criteria']], 'questions': []}

    def test_all_actual_wire_images_match_bytes_and_causal_times(self):
        counts=[]
        for i in range(6):
            cp, body, rows = self.request(i)
            media=[x['image_url']['url'] for x in body['messages'][1]['content'] if x['type']=='image_url']
            self.assertEqual(len(media),len(rows));counts.append(len(rows))
            for url,row in zip(media,rows):
                raw=base64.b64decode(url.split(',',1)[1])
                self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
                self.assertLessEqual(row['time'],cp['time'])
            self.assertEqual([r['path'] for r in rows if r['role']=='current'],[cp['image']])
        self.assertEqual(counts,[3,5,6,7,9,10])

    def test_context_has_source_order_rules_but_no_fixture_results(self):
        _,body,_=self.request(5)
        ctx=json.loads(body['messages'][1]['content'][0]['text'])
        self.assertEqual(len(ctx['criteria']),5)
        self.assertEqual(ctx['expectedTaskOrder'],self.scenario['tasks'])
        self.assertIn('7. S1을 켠다.',ctx['sourceSopExcerpt'])
        self.assertIn('8. S2를 켠다.',ctx['sourceSopExcerpt'])
        self.assertNotIn('assessments',ctx)
        self.assertNotIn('verdict',json.dumps(ctx))
        self.assertNotIn('sourceNote',ctx)
        self.assertNotIn('fixture',ctx['sourceSopExcerpt'])

    def test_prior_response_transport_is_explicit_and_no_assumed_future(self):
        prior=[{'sourceTime':20.361,'output':{'observedTaskId':None,'summaryKo':'모르겠습니다.'}}]
        _,body,_=self.request(1,prior)
        ctx=json.loads(body['messages'][1]['content'][0]['text'])
        self.assertEqual(ctx['priorModelObservations'],prior)

    def test_schema_accepts_unknown_and_literal_negative(self):
        cp,rows,output=self.output();capture.validate_output(output,self.scenario,cp,rows)
        output['assessments'][0]['observation']='absent'
        output['assessments'][0]['applicability']='due'
        output['assessments'][0]['reason']='시각적으로 확인한 반대 증거입니다.'
        capture.validate_output(output,self.scenario,cp,rows)

    def test_duplicate_missing_head_is_rejected(self):
        cp,rows,output=self.output();output['assessments'][1]=copy.deepcopy(output['assessments'][0])
        with self.assertRaises(AssertionError):capture.validate_output(output,self.scenario,cp,rows)

    def test_unknown_evidence_is_rejected(self):
        cp,rows,output=self.output();output['assessments'][0]['evidenceIds']=['future-frame']
        with self.assertRaises(Exception):capture.validate_output(output,self.scenario,cp,rows)

    def test_assertion_without_pixels_is_rejected(self):
        cp,rows,output=self.output();row=output['assessments'][0]
        row['observation']='present';row['evidenceIds']=[];row['targetConfirmed']=False
        with self.assertRaises(AssertionError):capture.validate_output(output,self.scenario,cp,rows)

    def test_wrong_target_is_rejected(self):
        cp,rows,output=self.output();output['assessments'][0]['target']='other-board'
        with self.assertRaises(Exception):capture.validate_output(output,self.scenario,cp,rows)

    def test_final_verdict_injection_is_rejected(self):
        cp,rows,output=self.output();output['assessments'][0]['verdict']='met'
        with self.assertRaises(Exception):capture.validate_output(output,self.scenario,cp,rows)

    def test_korean_explanation_is_required(self):
        cp,rows,output=self.output();output['summaryKo']='unknown'
        with self.assertRaises(AssertionError):capture.validate_output(output,self.scenario,cp,rows)


if __name__=='__main__':unittest.main()
