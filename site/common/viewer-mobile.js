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
