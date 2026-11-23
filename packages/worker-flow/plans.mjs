/** Select a pinned classroom plan without rewriting saved observations. */
import * as current from './plan.mjs';
import * as legacy from './plan-v1.mjs';

export function planForVersion(version=current.PLAN_VERSION){
 if(version===current.PLAN_VERSION)return current;
 if(version===legacy.PLAN_VERSION)return legacy;
 throw new Error('지원하지 않는 작업자 실습 계획입니다.');
}
export function planForState(state){
 return planForVersion(state?.planVersion??current.PLAN_VERSION);
}
