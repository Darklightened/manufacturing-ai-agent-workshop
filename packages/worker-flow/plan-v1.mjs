/** Authored classroom segmentation and checks; not model or original dataset annotations. */
export const PLAN_VERSION = 'electronics-worker-tablet-v1';
export const SOURCE_VIDEO = 'data/source_pack/electronics/S1790005/S1790005.mp4';
export const SOURCE_DURATION = 121.021;
const frame = name => `data/source_pack/electronics/S1790005/${name}`;
const check = (id, label, threshold, imageName, imageTime, reason, extra={}) => ({id,label,threshold,imagePath:frame(imageName),imageTime,reason,...extra});
const plans = [
 {id:'preparation',label:'부품과 작업 준비',sourceStart:0,sourceEnd:12,criterionId:'E-PREP',checks:[
  check('W-PREP-01','작업 보드와 지시서 준비',.1,'frame_00_0000.500s.jpg',.5,'작업 보드와 지시서가 준비된 것으로 설정한 예시입니다.'),
  check('W-PREP-02','연결 부품·모터·프로펠러 준비',.8,'frame_01_0009.220s.jpg',9.22,'조립에 필요한 부품 목록을 확인하는 예시입니다.'),
  check('W-PREP-03','배터리와 작업 공간 준비',1,'frame_01_0009.220s.jpg',9.22,'배터리와 작업 공간의 준비 확인을 기록했습니다.')
 ]},
 {id:'circuit',label:'회로 연결',sourceStart:12,sourceEnd:76.731,criterionId:'E-CONNECTION',checks:[
  check('W-CIRCUIT-01','지시서의 보드 위치와 부품 배치 대조',.2,'frame_02_0020.361s.jpg',20.361,'부품 배치를 지시서와 대조하는 강의용 확인입니다.'),
  check('W-CIRCUIT-02','연결 부품 체결 위치 확인',.6,'frame_03_0047.073s.jpg',47.073,'연결 부품이 지정 위치에 체결된 것으로 설정했습니다.'),
  check('W-CIRCUIT-03','회로 연결 완료와 누락 부품 확인',1,'frame_04_0076.731s.jpg',76.731,'회로 연결 완료와 빠진 연결 부품이 없는지 확인하는 예시입니다.')
 ]},
 {id:'propeller',label:'프로펠러 장착',sourceStart:76.731,sourceEnd:99.726,criterionId:'E-PROPELLER',checks:[
  check('W-PROPELLER-01','프로펠러와 모터 축 위치 확인',.6,'frame_05_0089.659s.jpg',89.659,'프로펠러의 장착 대상 모터 축을 확인했습니다.'),
  check('W-PROPELLER-02','프로펠러 삽입 상태 확인',.8,'frame_05_0089.659s.jpg',89.659,'프로펠러 삽입 상태 확인을 위한 강의용 판정입니다.'),
  check('W-PROPELLER-03','장착 완료 상태 기록',1,'frame_06_0099.726s.jpg',99.726,'장착 완료 후 다음 작업으로 이동하는 예시입니다.')
 ]},
 {id:'battery',label:'배터리 삽입',sourceStart:99.726,sourceEnd:108,criterionId:'E-BATTERY',checks:[
  check('W-BATTERY-01','배터리 홀더와 삽입 대상 확인',.15,'frame_06_0099.726s.jpg',99.726,'같은 회로 보드의 배터리 홀더에 연결했습니다.'),
  check('W-BATTERY-02','배터리 두 개 삽입 상태 확인',.9,'frame_07_0106.996s.jpg',106.996,'두 개의 배터리를 삽입한 것으로 설정한 강의용 예시입니다.'),
  check('W-BATTERY-03','배터리 + / − 방향과 홀더 표시 일치',1,'frame_07_0106.996s.jpg',106.996,'방향 표시가 손과 홀더에 가려져 영상만으로 확인하지 못했습니다.',{rawVerdict:'unknown',allowWorker:true,question:'배터리 두 개의 + / − 방향이 홀더 표시와 맞나요? 직접 확인한 뒤 답해 주세요.'})
 ]},
 {id:'switch',label:'스위치 확인',sourceStart:108,sourceEnd:116,criterionId:'E-SWITCH',checks:[
  check('W-SWITCH-01','S1 스위치 위치 확인',.8,'frame_08_0113.870s.jpg',113.87,'S1 위치 확인을 기록하는 강의용 예시입니다.'),
  check('W-SWITCH-02','S1 이후 S2 확인 순서 기록',.9,'frame_08_0113.870s.jpg',113.87,'S1 이후 S2 순서로 확인한 것으로 설정했습니다.'),
  check('W-SWITCH-03','스위치 점검 완료 기록',1,'frame_08_0113.870s.jpg',113.87,'스위치 점검 완료 신호를 기록했습니다.')
 ]},
 {id:'final',label:'최종 외관 기록',sourceStart:116,sourceEnd:121.0,criterionId:'E-FINAL',checks:[
  check('W-FINAL-01','조립 완료 외관 확인',.82,'frame_09_0120.021s.jpg',120.021,'조립 완료 외관을 기록하는 강의용 확인입니다.'),
  check('W-FINAL-02','최종 장면과 작업 대상 연결',.92,'frame_09_0120.021s.jpg',120.021,'최종 장면을 현재 작업 지시와 연결했습니다.'),
  check('W-FINAL-03','검사 결과·답변·증거 기록 확보',1,'frame_09_0120.021s.jpg',120.021,'검사 결과와 확인 답변을 검수조서에 연결할 준비가 되었습니다.')
 ]}
];
function deepFreeze(x){Object.freeze(x);for(const v of Object.values(x))if(v&&typeof v==='object'&&!Object.isFrozen(v))deepFreeze(v);return x;}
export const PLAN = deepFreeze(plans.map((stage,index)=>({...stage,index,taskId:stage.id,sourceVideo:SOURCE_VIDEO,imagePath:stage.checks.at(-1).imagePath,origin:'authored_demo',checks:stage.checks.map(c=>({...c,criterionId:stage.criterionId,taskId:stage.id,target:'circuit-board',origin:'authored_demo',rawVerdict:c.rawVerdict||'met',allowWorker:!!c.allowWorker}))})));
export const CHECKS = deepFreeze(PLAN.flatMap(stage=>stage.checks));
export const PROCESS = deepFreeze({id:'ELEC-DEMO-001',companyId:'edu-daon',label:'바람빛 회로 키트 조립',orderId:'DEMO-001',productName:'바람빛 회로 키트',quantity:1});
