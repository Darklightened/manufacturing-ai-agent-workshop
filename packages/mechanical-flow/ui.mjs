import * as Core from '../core/core.mjs';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clock = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
const labels = {met:'충족',violated:'불일치',unknown:'확인 필요',not_due:'예정',unassessed:'확인 전'};
const finished = q => ['resolved','superseded'].includes(q.state);

/** The UI stage is not a second inspection ledger; all saved decisions use Core. */
export function stageGate(session, scenario, index) {
  const cp = scenario.checkpoints[index];
  if (!session || !cp || session.position < index) return false;
  const tasks = new Set(scenario.checkpoints.slice(0,index + 1).map(c => c.taskId));
  return session.bundle.criteria.filter(c => tasks.has(c.taskId)).every(c => session.assessments[c.id]?.verdict === 'met')
    && !session.questions.some(q => tasks.has(q.taskId) && !finished(q));
}
export function restoredStage(session, scenario) {
  return Math.max(0, Math.min(session?.position ?? -1, scenario.checkpoints.length - 1));
}

export class MechanicalExperience {
  constructor(host) {
    this.host = host; this.index = 0; this.speed = 2; this.key = null;
    this.video = null; this.generation = 0; this.busy = false; this.pendingCriterion = null; this.view = 'operator';
  }
  reset() { this.leave(); this.key = null; this.index = 0; this.pendingCriterion = null; this.view = 'operator'; }
  focusCriterion(criterionId) { this.pendingCriterion = criterionId; }
  leave() {
    if (typeof document !== 'undefined') document.body.classList.remove('operator-active');
    this.generation++;
    const video = this.video;
    if (video) {
      video.pause();
      for (const name of ['onloadedmetadata','ontimeupdate','onseeking','onseeked','onended','onplay','onpause','onerror']) video[name] = null;
      if (this.frameCallback && video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(this.frameCallback);
    }
    this.frameCallback = null; this.video = null;
  }
  action(fn) {
    return async event => {
      if (this.busy) return;
      this.busy = true;
      try { await fn(event); } catch (error) { this.host.toast(error.message); }
      finally { this.busy = false; }
    };
  }
  async commit(next) { await this.host.commit(next); }
  render() {
    this.leave();
    const {main} = this.host, s = this.host.session(), scenario = this.host.scenario();
    if (!s) { this.host.navigate('setup'); return; }
    const key = `${scenario.id}:${s.id}`;
    if (this.key !== key) { this.key = key; this.index = restoredStage(s,scenario); this.view = 'operator'; }
    if (this.pendingCriterion) {
      const taskId = scenario.criteria.find(c => c.id === this.pendingCriterion)?.taskId;
      const index = scenario.checkpoints.findIndex(cp => cp.taskId === taskId);
      if (index >= 0 && index <= s.position) this.index = index;
      this.pendingCriterion = null;
    }
    this.index = Math.max(0,Math.min(this.index,Math.min(s.position + 1,scenario.checkpoints.length - 1)));
    const cp = scenario.checkpoints[this.index], done = s.position >= this.index;
    const taskLabel = scenario.tasks.find(t => t.id === cp.taskId)?.label;
    main.innerHTML = `<div class="mechanical-flow mechanical-${this.view}">
      <header class="mechanical-workspace-bar"><div class="mechanical-workspace-title"><span class="mechanical-wordmark">DYNIN</span><span id="mechanical-view-label">작업자 화면</span><span class="mechanical-order">${esc(scenario.orderId)} · ${esc(scenario.productName)}</span></div><button id="mechanical-view-switch" class="secondary" type="button">모니터링 화면 ↗</button></header>
      <div class="mechanical-monitor-title"><div><p>${esc(scenario.companyName)} / ${esc(scenario.processId)}</p><h1>조립 작업 모니터링</h1></div><span>${esc(scenario.orderId)} · 작업 기록</span></div>
      <nav class="mechanical-stage-strip" aria-label="조립 작업 단계">${scenario.checkpoints.map((p,i) => `<button type="button" data-stage="${i}" class="${i === this.index ? 'current' : ''} ${stageGate(s,scenario,i) ? 'done' : ''}" ${i > s.position ? 'disabled' : ''}><span>${stageGate(s,scenario,i) ? '✓' : i + 1}</span><strong>${esc(scenario.tasks.find(t => t.id === p.taskId)?.label)}</strong><small>${clock(p.sourceStart)}–${clock(p.sourceEnd)}</small></button>`).join('')}</nav>
      <div class="mechanical-layout">
        <section class="mechanical-video-panel">
          <div class="mechanical-camera"><video id="mechanical-video" playsinline preload="metadata" poster="${esc(cp.image)}" src="${esc(cp.videoPath)}" aria-label="현재 작업 단계의 조립 영상"></video><div class="mechanical-camera-top"><span class="mechanical-camera-badge"><i></i> 작업 영상</span><span id="mechanical-video-clock">${clock(done ? cp.sourceEnd : cp.sourceStart)} / ${clock(cp.sourceEnd)}</span></div><div class="mechanical-camera-bottom"><span>작업 ${String(this.index + 1).padStart(2,'0')} / ${String(scenario.checkpoints.length).padStart(2,'0')}</span><h2>${esc(taskLabel)}</h2><p>${esc(cp.sceneSummary.replace('단계 마지막에는','마지막에'))}</p></div></div>
          <div class="mechanical-progress" role="progressbar" aria-label="현재 단계 영상 진행" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${done ? 100 : 0}"><span id="mechanical-video-progress" style="width:${done ? 100 : 0}%"></span></div>
          <div class="mechanical-video-controls"><button id="mechanical-play" class="secondary">${done ? '단계 다시 보기' : '영상 재생'}</button><label>재생 속도 <select id="mechanical-speed" aria-label="기계 조립 영상 재생 속도">${[1,2,4].map(rate => `<option value="${rate}" ${rate === this.speed ? 'selected' : ''}>${rate}배</option>`).join('')}</select></label><div class="mechanical-actions"><button id="mechanical-next" class="primary" disabled>검사 기록 확인</button><button id="mechanical-review" class="secondary" ${s.position < 0 ? 'disabled' : ''}>현재 검수 기록</button></div></div>
          <div id="mechanical-video-error" role="status"></div>
        </section>
        <aside class="mechanical-inspection">
          <div class="mechanical-live-notices"><div id="mechanical-signal" class="mechanical-signal" role="status" aria-live="polite"></div><section id="mechanical-questions" class="mechanical-question-box"></section><section id="mechanical-guidance" class="mechanical-guidance" aria-live="polite" hidden></section></div>
          <section class="mechanical-check-panel"><div class="section-row"><h2>현재 단계 검사 결과</h2><span id="mechanical-check-count" class="tag"></span></div><div id="mechanical-checks"></div><p class="hint mechanical-scope">${esc(cp.scopeNote.replace(' 예시',''))}</p></section>
        </aside>
      </div>
      <section class="mechanical-journal"><div class="section-row"><h2>작업 이력</h2><span>영상 시각 · 확인 결과 · 작업자 답변</span></div><div id="mechanical-events"></div></section>
    </div>`;
    main.querySelector('#mechanical-view-switch').onclick = () => this.setView(this.view === 'operator' ? 'monitor' : 'operator');
    this.mountVideo(cp,done);
    main.querySelectorAll('[data-stage]').forEach(button => button.onclick = () => { this.index = Number(button.dataset.stage); this.render(); });
    main.querySelector('#mechanical-next').onclick = this.action(async () => {
      const state = this.host.session();
      if (!stageGate(state,scenario,this.index)) throw new Error('이 단계와 앞 단계의 확인이 모두 끝나야 진행할 수 있습니다.');
      if (this.view === 'operator') { this.setView('monitor'); return; }
      if (this.index === scenario.checkpoints.length - 1) { this.host.navigate('review'); return; }
      this.index++; this.view = 'operator'; this.render();
      try { await this.video?.play(); } catch { /* The user can press play when autoplay is unavailable. */ }
    });
    main.querySelector('#mechanical-review').onclick = () => this.host.navigate('review');
    this.setView(this.view);
    this.update();
  }
  setView(view) {
    this.view = view === 'monitor' ? 'monitor' : 'operator';
    const main = this.host.main, operator = this.view === 'operator';
    main.querySelector('.mechanical-flow')?.classList.toggle('mechanical-operator',operator);
    main.querySelector('.mechanical-flow')?.classList.toggle('mechanical-monitor',!operator);
    document.body.classList.toggle('operator-active',operator);
    main.querySelector('#mechanical-view-switch').textContent = operator ? '모니터링 화면 ↗' : '작업자 화면으로';
    main.querySelector('#mechanical-view-label').textContent = operator ? '작업자 화면' : '모니터링';
    this.update();
    window.scrollTo(0,0);
  }
  mountVideo(cp,done) {
    const {main} = this.host, video = main.querySelector('#mechanical-video');
    this.video = video; const generation = this.generation;
    let ready = false, initializing = true, correcting = false;
    let allowed = done ? cp.sourceEnd : cp.sourceStart;
    let lastTime = allowed, lastWall = performance.now(), completing = false;
    video.playbackRate = this.speed;
    const live = () => this.video === video && this.generation === generation && video.isConnected;
    const init = () => {
      if (!live()) return;
      initializing = true;
      video.currentTime = done ? Math.min(cp.sourceEnd,video.duration) : cp.sourceStart;
      ready = true; lastTime = video.currentTime; lastWall = performance.now();
      // Metadata seek is a known setup operation. No observation is saved here.
      if (!video.seeking) initializing = false;
    };
    video.onloadedmetadata = init;
    video.onseeked = () => { initializing = false; correcting = false; lastTime = video.currentTime; lastWall = performance.now(); };
    if (video.readyState >= 1) init();
    video.onseeking = () => {
      if (!ready || !live() || initializing || correcting) return;
      if (video.currentTime > allowed + .12 || video.currentTime < cp.sourceStart) {
        correcting = true; video.currentTime = Math.max(cp.sourceStart,allowed);
        this.host.toast('아직 보지 않은 구간은 영상 재생 후 확인합니다.');
      }
    };
    const observe = async () => {
      if (!ready || !live() || initializing || correcting || video.seeking || completing) return;
      const time = video.currentTime, now = performance.now();
      // Ignore abrupt forward jumps, including programmatic seeks. Only video
      // playback reaching the stage end can commit a new checkpoint.
      const plausible = time <= lastTime + Math.max(.7,(now - lastWall) / 1000 * video.playbackRate + .35);
      if (!plausible && time > allowed + .12) return;
      lastTime = time; lastWall = now;
      allowed = Math.max(allowed,Math.min(time,cp.sourceEnd));
      const percent = Math.min(100,Math.max(0,(time - cp.sourceStart) / (cp.sourceEnd - cp.sourceStart) * 100));
      const bar = main.querySelector('#mechanical-video-progress');
      bar.style.width = `${percent}%`;bar.parentElement.setAttribute('aria-valuenow',String(Math.round(percent)));
      main.querySelector('#mechanical-video-clock').textContent = `${clock(Math.min(time,cp.sourceEnd))} / ${clock(cp.sourceEnd)}`;
      if (time >= cp.sourceEnd) {
        video.pause();
        const state = this.host.session();
        if (state.position >= this.index) { main.querySelector('#mechanical-play').textContent = '단계 다시 보기'; return; }
        if (state.position !== this.index - 1) return;
        completing = true;
        try {
          await this.commit(Core.advance(state,this.host.scenario(),this.index));
          if (live()) { this.update(); main.querySelector('#mechanical-review').disabled = false; main.querySelector('#mechanical-play').textContent = '단계 다시 보기'; }
        } catch (error) { this.host.toast(error.message); }
        finally { completing = false; }
      }
    };
    video.ontimeupdate = () => { void observe(); };
    video.onended = () => { void observe(); };
    if (video.requestVideoFrameCallback) {
      const frame = () => { if (!live()) return; void observe(); this.frameCallback = video.requestVideoFrameCallback(frame); };
      this.frameCallback = video.requestVideoFrameCallback(frame);
    }
    video.onplay = () => { lastTime = video.currentTime;lastWall = performance.now();if(live()) main.querySelector('#mechanical-play').textContent = '일시정지'; };
    video.onpause = () => { if(live()) main.querySelector('#mechanical-play').textContent = this.host.session().position >= this.index ? '단계 다시 보기' : '영상 재생'; };
    video.onerror = () => { if(live()) main.querySelector('#mechanical-video-error').innerHTML = '<div class="notice warning">영상을 불러오지 못했습니다. 네트워크를 확인하고 다시 재생해 주세요. 영상 없이 검사를 완료하지 않습니다.</div>'; };
    main.querySelector('#mechanical-play').onclick = this.action(async () => {
      if (!ready) throw new Error('영상이 준비되는 중입니다. 잠시 후 다시 눌러 주세요.');
      if (video.paused) {
        if (video.currentTime >= cp.sourceEnd - .1) { initializing = true;video.currentTime = cp.sourceStart;allowed = this.host.session().position >= this.index ? cp.sourceEnd : cp.sourceStart;lastTime = cp.sourceStart; }
        await video.play();
      } else video.pause();
    });
    main.querySelector('#mechanical-speed').onchange = event => { this.speed = Number(event.target.value);video.playbackRate = this.speed;lastTime = video.currentTime;lastWall = performance.now(); };
  }
  update() {
    const {main} = this.host, s = this.host.session(), scenario = this.host.scenario(), cp = scenario.checkpoints[this.index];
    if (!main.querySelector('#mechanical-checks')) return;
    const summary = Core.summarize(s,scenario), rows = summary.rows.filter(c => c.taskId === cp.taskId), canNext = stageGate(s,scenario,this.index);
    main.querySelector('#mechanical-check-count').textContent = `${rows.filter(r => r.verdict === 'met').length} / ${rows.length} 확인`;
    main.querySelector('#mechanical-checks').innerHTML = rows.map(r => `<div class="mechanical-check ${esc(r.verdict)}"><span>${r.verdict === 'met' ? '✓' : r.verdict === 'violated' ? '!' : r.verdict === 'unknown' ? '?' : '·'}</span><div><strong>${esc(r.label)}</strong><small>${esc(labels[r.verdict])}${r.origin ? ` · ${r.origin === 'worker_confirmed' ? '작업자 확인' : '영상 확인'}` : ''}</small>${r.reason ? `<p>${esc(r.reason)}</p>` : ''}</div></div>`).join('');
    const signal = main.querySelector('#mechanical-signal');
    signal.className = 'mechanical-signal ' + (canNext ? 'passed' : s.position >= this.index ? 'held' : '');
    signal.innerHTML = canNext ? '<span class="mechanical-notice-source">DYNIN · 검사 완료</span><strong>✓ 이번 작업을 통과했습니다</strong><span>검사 기록을 확인한 뒤 다음 작업으로 이동하세요.</span>' : s.position >= this.index ? '<span class="mechanical-notice-source">DYNIN · 확인 요청</span><strong>작업을 잠시 멈춰 주세요</strong><span>확인이 필요한 항목이 남아 있습니다.</span>' : '<span class="mechanical-notice-source">DYNIN · 작업 진행</span><strong>작업 장면을 확인하고 있습니다</strong><span>확인이 필요한 항목은 이곳에서 안내합니다.</span>';
    main.querySelector('#mechanical-next').disabled = !canNext;
    main.querySelector('#mechanical-next').textContent = this.view === 'operator' ? '검사 기록 확인 →' : this.index === scenario.checkpoints.length - 1 ? '검수 완료 · 결과 보기' : '다음 작업 시작 →';
    main.querySelectorAll('[data-stage]').forEach(button => {
      const index = Number(button.dataset.stage), pass = stageGate(s,scenario,index);
      button.disabled = index > s.position;button.classList.toggle('done',pass);
      button.querySelector('span').textContent = pass ? '✓' : String(index + 1);
    });
    this.questions();this.guidance();this.events();
  }
  questions() {
    const {main} = this.host, s = this.host.session(), cp = this.host.scenario().checkpoints[this.index];
    const box = main.querySelector('#mechanical-questions'), questions = s.questions.filter(q => q.taskId === cp.taskId);
    box.hidden = !questions.length;
    box.innerHTML = '<h2>연결 핀 확인</h2>' + (questions.length ? questions.map(q => `<article class="mechanical-question"><p><strong>${esc(s.assessments[q.criterionId]?.proposedQuestion ?? q.text)}</strong></p>${finished(q) ? '<span class="tag">답변 기록됨</span>' : !q.deliveredChannels.length ? `<button class="primary" data-deliver="${esc(q.id)}">질문 확인</button>` : `<p class="hint">직접 확인한 결과를 선택해 주세요.</p><div class="mechanical-replies">${[['met','핀을 제자리에 끼운 것을 확인했습니다'],['violated','핀이 제대로 끼워지지 않았습니다'],['unknown','아직 확인할 수 없습니다']].map(([value,text]) => `<button class="secondary" data-answer="${esc(q.id)}" data-confirmation="${value}">${text}</button>`).join('')}</div>`}${q.answers.length ? `<details><summary>답변 이력</summary>${q.answers.map(a => `<p class="hint">${esc(a.text)} · ${esc(labels[a.confirmation])}</p>`).join('')}</details>` : ''}${q === questions.at(-1) && finished(q) ? `<button class="quiet" data-reopen="${esc(q.criterionId)}">핀 상태 다시 확인</button>` : ''}</article>`).join('') : '<p class="hint">이 단계에서 가려진 항목이 발견되면 확인 요청을 표시합니다.</p>');
    box.querySelectorAll('[data-deliver]').forEach(button => button.onclick = this.action(async () => { await this.commit(Core.markDelivered(this.host.session(),button.dataset.deliver,'screen'));this.update(); }));
    box.querySelectorAll('[data-answer]').forEach(button => button.onclick = this.action(async () => {
      const q = this.host.session().questions.find(q => q.id === button.dataset.answer);
      await this.commit(Core.answerQuestion(this.host.session(),q.id,{target:q.target,confirmation:button.dataset.confirmation,text:button.textContent}));this.update();
    }));
    box.querySelectorAll('[data-reopen]').forEach(button => button.onclick = this.action(async () => { await this.commit(Core.reopenQuestion(this.host.session(),button.dataset.reopen));this.update(); }));
  }
  guidance() {
    const box = this.host.main.querySelector('#mechanical-guidance');
    const s = this.host.session(), scenario = this.host.scenario(), cp = scenario.checkpoints[this.index];
    const guidance = s.events.find(e => e.type === 'task_guidance' && e.afterCheckpointId === cp.id);
    const canAsk = this.index === s.position && this.index < scenario.checkpoints.length - 1 && stageGate(s,scenario,this.index);
    box.hidden = !guidance && !canAsk;
    box.innerHTML = guidance ? `<div class="mechanical-guidance-dialog"><div class="mechanical-guidance-question"><small>작업자</small><p>${esc(guidance.question)}</p></div><div class="mechanical-guidance-answer"><small>Agent · 작업 절차 안내</small><p>${esc(guidance.answer)}</p>${guidance.scopeNote ? `<p class="hint">${esc(guidance.scopeNote.replace(' 예시',''))}</p>` : ''}</div></div>` : canAsk ? '<button id="mechanical-ask-guidance" class="quiet">다음 작업은 어떻게 하나요?</button>' : '';
    const button = box.querySelector('#mechanical-ask-guidance');
    if (button) button.onclick = this.action(async () => {
      await this.commit(Core.requestTaskGuidance(this.host.session(),this.host.scenario()));this.update();
    });
  }
  events() {
    const s = this.host.session(), scenario = this.host.scenario();
    const names = {checkpoint:'단계 관찰 기록',question_delivered:'질문 확인',answer:'작업자 답변 기록',question_reopened:'핀 상태 재확인',worker_policy_changed:'확인 근거 변경',task_guidance:'다음 작업 절차 안내'};
    this.host.main.querySelector('#mechanical-events').innerHTML = s.events.length ? `<ol>${s.events.map(event => `<li><time>${clock(event.time ?? 0)}</time><span>${esc(names[event.type] ?? event.type)}${event.type === 'checkpoint' ? ` · ${esc(scenario.tasks.find(t => t.id === event.taskId)?.label ?? '')}` : ''}${event.type === 'task_guidance' ? ` · ${esc(event.nextTaskLabel)}` : event.answer ? ` · ${esc(event.answer.text)}` : ''}</span></li>`).join('')}</ol>` : '<p class="hint">영상이 단계 끝까지 재생되면 관찰과 증거 사진을 저장합니다.</p>';
  }
}
