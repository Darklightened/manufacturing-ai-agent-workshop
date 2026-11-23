/** Authored classroom checks aligned to actual source scenes; not model predictions. */
export const PLAN_VERSION = 'electronics-worker-tablet-v2';
export const SOURCE_VIDEO = 'data/source_pack/electronics/S1790005/S1790005.mp4';
export const SOURCE_DURATION = 121.021;
const frame = name => name.startsWith('frame_0') && name.includes('s.jpg') ? `data/source_pack/electronics/S1790005/${name}` : `assets/worker-flow/alignment-v2/${name}`;
const check = (id, label, threshold, imageName, imageTime, reason, extra={}) => ({id,label,threshold,imagePath:frame(imageName),imageTime,reason,...extra});
const plans = [
 {id:'preparation',label:'부품과 작업 준비',sourceStart:0,sourceEnd:2.2,criterionId:'E-PREP',sceneSummary:'시작 장면의 보드·지시서·부품을 확인합니다. 이어서 바로 조립이 시작됩니다.',checks:[
  check('W-PREP-01','작업 보드와 지시서 준비',.3,'frame_00_0000.500s.jpg',.5,'가운데 작업 보드와 오른쪽 지시서가 보입니다.'),
  check('W-PREP-02','연결 부품·모터·프로펠러 준비',.7,'frame_00_0000.500s.jpg',.5,'보드 위쪽에 연결 부품과 모터 부품, 빨간 프로펠러가 놓여 있습니다.'),
  check('W-PREP-03','배터리 두 개와 조립 공간 확보',1,'frame_00_0000.500s.jpg',.5,'배터리 두 개가 놓여 있고 보드의 조립 공간이 비어 있습니다.')
 ]},
 {id:'circuit',label:'회로 연결',sourceStart:2.2,sourceEnd:85.5,criterionId:'E-CONNECTION',sceneSummary:'배터리 홀더부터 스위치·모터·램프와 연결 부품을 차례로 조립합니다.',scopeNote:'부품 배치와 연결 동작을 확인하는 예시입니다. 통전·접촉 저항 등 전기적 성능은 별도 검사 대상입니다.',checks:[
  check('W-CIRCUIT-01','배터리 홀더와 첫 스위치 배치',.18,'frame_016.jpg',16,'보드에 배터리 홀더를 놓고 첫 스위치 부품을 연결하는 장면입니다.'),
  check('W-CIRCUIT-02','모터·램프·스위치 주변 연결',.78,'frame_066.jpg',66,'모터와 녹색 부품 주변에 파란 연결 부품을 이어 붙이는 장면입니다.'),
  check('W-CIRCUIT-03','마지막 연결 부품 장착',1,'frame_085.jpg',85,'마지막 연결 부품을 장착한 뒤 프로펠러 작업으로 넘어갑니다. 전체 부품 누락이나 전기적 정상 여부까지 확정하는 검사는 아닙니다.')
 ]},
 {id:'propeller',label:'프로펠러 장착',sourceStart:85.5,sourceEnd:93.5,criterionId:'E-PROPELLER',sceneSummary:'빨간 프로펠러를 집어 모터 축에 맞춘 뒤 장착합니다.',checks:[
  check('W-PROPELLER-01','프로펠러를 모터 위로 이동',.25,'frame_087.jpg',87,'빨간 프로펠러를 집어 모터 위로 가져옵니다.'),
  check('W-PROPELLER-02','모터 축에 프로펠러 삽입',.75,'frame_091.jpg',91,'프로펠러 중심을 축에 맞추며 삽입하는 장면입니다.'),
  check('W-PROPELLER-03','프로펠러 장착 상태 확인',1,'frame_093.jpg',93,'손을 뗀 뒤 프로펠러가 모터 위에 장착된 상태가 보입니다.')
 ]},
 {id:'battery',label:'배터리 삽입',sourceStart:93.5,sourceEnd:105.7,criterionId:'E-BATTERY',sceneSummary:'배터리 두 개를 홀더에 넣습니다. 작게 보이는 극성 표시는 작업자에게 확인합니다.',checks:[
  check('W-BATTERY-01','배터리 두 개를 집어 준비',.15,'frame_095.jpg',95,'작업자가 배터리 두 개를 집어 홀더 쪽으로 가져옵니다.'),
  check('W-BATTERY-02','홀더 안 배터리 두 개 확인',.95,'frame_105.jpg',105,'두 배터리를 차례로 삽입한 뒤 홀더 안에 놓인 상태가 보입니다.'),
  check('W-BATTERY-03','배터리 + / − 방향과 홀더 표시 일치',1,'frame_105.jpg',105,'배터리 몸체는 보이지만 + / − 표시가 작고 일부 가려져 방향을 확정하기 어렵습니다.',{rawVerdict:'unknown',allowWorker:true,question:'배터리 두 개의 + / − 방향이 홀더 표시와 맞나요? 직접 확인한 뒤 답해 주세요.'})
 ]},
 {id:'switch',label:'스위치 확인',sourceStart:105.7,sourceEnd:119.3,criterionId:'E-SWITCH',sceneSummary:'첫 스위치 조작에 이어 다른 스위치를 조작하는 장면입니다. 프로펠러의 움직임도 관찰합니다.',scopeNote:'S1·S2 이름은 원본 작업 순서 주석을 따른 안내입니다. 화면에서 작은 글자를 OCR로 읽은 결과는 아닙니다.',checks:[
  check('W-SWITCH-01','첫 번째 스위치(S1) 조작',.18,'frame_107.jpg',107,'첫 스위치 조작 구간입니다. 이어지는 영상에서 프로펠러가 회전합니다.'),
  check('W-SWITCH-02','두 번째 스위치(S2) 조작',.65,'frame_114.jpg',114,'첫 스위치 다음에 다른 스위치를 조작합니다. S1·S2 명칭은 원본 순서 주석에 맞췄습니다.'),
  check('W-SWITCH-03','스위치 조작 종료 장면 기록',1,'frame_119.jpg',119,'스위치 조작을 마치고 손을 떼기 시작하는 장면을 기록합니다.')
 ]},
 {id:'final',label:'최종 외관 기록',sourceStart:119.3,sourceEnd:121.0,criterionId:'E-FINAL',sceneSummary:'손을 치운 최종 외관을 저장하고, 지금까지의 확인 내용과 답변을 보고서에 모읍니다.',checks:[
  check('W-FINAL-01','손을 치운 조립 외관 확인',.5,'frame_09_0120.021s.jpg',120.021,'손을 보드 바깥으로 옮겨 조립된 보드 전체가 보입니다.'),
  check('W-FINAL-02','최종 사진을 이번 작업에 연결',.8,'frame_09_0120.021s.jpg',120.021,'같은 영상의 최종 사진을 이번 작업 기록에 연결합니다.'),
  check('W-FINAL-03','검사 결과·답변·증거 기록 확보',1,'frame_09_0120.021s.jpg',120.021,'확인 결과와 작업자 답변, 증거 사진을 검수조서에 모읍니다.')
 ]}
];
function deepFreeze(x){Object.freeze(x);for(const v of Object.values(x))if(v&&typeof v==='object'&&!Object.isFrozen(v))deepFreeze(v);return x;}
export const PLAN = deepFreeze(plans.map((stage,index)=>({...stage,index,taskId:stage.id,sourceVideo:SOURCE_VIDEO,imagePath:stage.checks.at(-1).imagePath,origin:'authored_demo',checks:stage.checks.map(c=>({...c,criterionId:stage.criterionId,taskId:stage.id,target:'circuit-board',origin:'authored_demo',rawVerdict:c.rawVerdict||'met',allowWorker:!!c.allowWorker}))})));
export const CHECKS = deepFreeze(PLAN.flatMap(stage=>stage.checks));
export const PROCESS = deepFreeze({id:'ELEC-DEMO-001',companyId:'edu-daon',label:'바람빛 회로 키트 조립',orderId:'DEMO-001',productName:'바람빛 회로 키트',quantity:1});
