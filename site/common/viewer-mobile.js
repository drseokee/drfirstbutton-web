/* 3D 뷰어 — 아래쪽 막대(단계·조절·설명 문구)를 겹치지 않게 아래에서부터 차례로 쌓습니다.
   PC에서는 높이만 정리하고(가운데 정렬은 그대로), 휴대폰에서는 viewer-mobile.css 가 폭을 화면에 맞춥니다. */
(function () {
  const ORDER = ['foot', 'stages', 'subbar', 'drawerbar', 'ctl', 'twist', 'surg', 'caption'];   // 아래 → 위
  const els = ORDER.map(id => document.getElementById(id)).filter(Boolean);
  if (!els.length) return;
  const small = () => innerWidth <= 720 || innerHeight <= 520;
  const shown = el => getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden' && el.offsetHeight > 0 && (el.textContent.trim() || el.querySelector('input,button'));
  let queued = false, lastOn = null;
  function layout() {
    queued = false;
    const sm = small();
    let y = (sm ? 6 : 22) + (parseFloat(getComputedStyle(probe).paddingBottom) || 0);
    els.forEach(el => {
      if (el.id === 'foot' && !sm) { if (el.style.getPropertyValue('bottom')) el.style.removeProperty('bottom'); return; }   // PC: 출처 문구는 오른쪽 아래 그대로
      if (!shown(el)) return;
      if (el.style.getPropertyValue('bottom') !== y + 'px') el.style.setProperty('bottom', y + 'px', 'important');
      y += el.offsetHeight + (el.id === 'foot' ? 4 : 8);
    });
    // 지금 단계 버튼이 가로 스크롤 밖에 있으면 보이게
    const on = document.querySelector('#stages button.on');
    if (on && on !== lastOn) { lastOn = on; on.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' }); }
  }
  const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(layout); } };
  const probe = document.createElement('div');   // 아이폰 아래 홈 막대 높이 재기
  probe.style.cssText = 'position:fixed;visibility:hidden;pointer-events:none;padding-bottom:env(safe-area-inset-bottom)';
  document.body.append(probe);
  const mo = new MutationObserver(schedule);
  els.forEach(el => mo.observe(el, { attributes: true, attributeFilter: ['style', 'class', 'hidden'], childList: true, subtree: true, characterData: true }));
  addEventListener('resize', schedule); addEventListener('orientationchange', schedule);
  // 터치 태블릿·휴대폰: 처음엔 설정 패널을 접어 3D가 가려지지 않게
  if (matchMedia('(hover: none)').matches && innerWidth < 1100) document.querySelectorAll('#panel details[open]').forEach(d => d.removeAttribute('open'));
  schedule(); setTimeout(schedule, 500);
})();

/* 미니멀 (모든 기기)
   1) 왼쪽 설정 창은 항상 접힌 채로 시작 — 막대 아무 곳이나 누르면 펼쳐짐
   2) 설명 문구는 첫 문장만 — 누르면 전체, 다시 누르면 접힘
   3) 버튼 글자의 이모지는 뺌 */
(function () {
  const panel = document.getElementById('panel');
  const fold = () => document.querySelectorAll('#panel details[open]').forEach(d => d.removeAttribute('open'));
  fold(); setTimeout(fold, 0); addEventListener('load', () => setTimeout(fold, 0));
  if (panel) panel.addEventListener('click', e => {
    const d = panel.querySelector('details');
    if (d && !d.open && !e.target.closest('summary')) { d.open = true; e.preventDefault(); }
  });

  const cap = document.getElementById('caption');
  if (cap) {
    let full = '', shown = null, expanded = false;
    const first = s => { const m = s.match(/^[\s\S]*?(?:[.!?。](?=\s|$)|(?=\s—\s))/); return m && m[0].trim().length < s.trim().length ? m[0].trim() : null; };
    const render = () => {
      const short = expanded ? null : first(full); shown = short || full;
      if (cap.textContent !== shown) cap.textContent = shown;
      cap.classList.toggle('vm-short', !!short); cap.classList.toggle('vm-full', expanded && !!first(full));
    };
    new MutationObserver(() => {
      const t = cap.textContent; if (t === shown) return;
      if (t !== full) { full = t; expanded = false; }
      render();
    }).observe(cap, { childList: true, characterData: true, subtree: true });
    cap.addEventListener('click', () => { if (!first(full)) return; expanded = !expanded; render(); });
    full = cap.textContent; render();
  }

  const EMO = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B50}\u{FE0F}]\s*/gu;
  const clean = () => document.querySelectorAll('button').forEach(b => b.childNodes.forEach(n => { if (n.nodeType === 3) { const s = n.data.replace(EMO, ''); if (s !== n.data) n.data = s; } }));
  let q = false; clean();
  new MutationObserver(() => { if (!q) { q = true; requestAnimationFrame(() => { q = false; clean(); }); } })
    .observe(document.body, { childList: true, subtree: true, characterData: true });
})();

/* 두 손가락 비틀기(검지·중지를 돌리기) → 화면 회전.  기존 두 손가락 이동·확대와 함께 동작합니다.
   살짝 벌리거나 오므릴 때 화면이 돌지 않도록 처음 약 7°까지는 무시합니다. */
(function () {
  const cv = document.getElementById('c');
  if (!cv || typeof THREE === 'undefined') return;
  const ok = () => typeof up !== 'undefined' && typeof camera !== 'undefined' && typeof target !== 'undefined' && typeof applyCam === 'function';
  const ang = t => Math.atan2(t[1].clientY - t[0].clientY, t[1].clientX - t[0].clientX);
  let a0 = null, acc = 0, on = false;
  const wrap = d => (d > Math.PI ? d - 2 * Math.PI : d < -Math.PI ? d + 2 * Math.PI : d);
  cv.addEventListener('touchstart', e => { if (e.touches.length === 2) { a0 = ang(e.touches); acc = 0; on = false; } else a0 = null; }, { passive: true });
  cv.addEventListener('touchmove', e => {
    if (e.touches.length !== 2 || a0 === null || !ok()) return;
    const a = ang(e.touches), d = wrap(a - a0); a0 = a;
    if (!on) { acc += d; if (Math.abs(acc) < 0.12) return; on = true; }
    if (typeof camGoal !== 'undefined') camGoal.t = 1;
    const f = target.clone().sub(camera.position).normalize();
    up.applyQuaternion(new THREE.Quaternion().setFromAxisAngle(f, -d)).normalize(); applyCam();   // 손가락을 시계 방향으로 돌리면 모형도 시계 방향
  }, { passive: true });
  const end = e => { if (e.touches.length < 2) { a0 = null; on = false; } };
  cv.addEventListener('touchend', end, { passive: true }); cv.addEventListener('touchcancel', end, { passive: true });
})();

/* 단계(탭)를 넘겨도 보던 구도(각도·확대·위치)를 그대로 유지.  처음 열 때의 구도와 '원래대로'(R)는 그대로 동작합니다. */
(function () {
  if (typeof goStage !== 'function' || typeof off === 'undefined' || typeof up === 'undefined' || typeof target === 'undefined' || typeof applyCam !== 'function') return;
  const orig = goStage;
  goStage = function () {
    const o = off.clone(), u = up.clone(), t = target.clone();
    const r = orig.apply(this, arguments);
    if (typeof camGoal !== 'undefined') { camGoal.off.copy(o); camGoal.up.copy(u); camGoal.target.copy(t); camGoal.t = 1; }
    off.copy(o); up.copy(u); target.copy(t); applyCam();
    return r;
  };
})();
