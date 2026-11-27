/* 닥터첫단추 — 주사 치료 페이지. 내용은 common/injections.js 에 있습니다.
   카드 격자 → 카드를 누르면 화면 전체로 (진료실 모니터용). 주소 끝 #카드id 로 바로 열 수 있습니다 (예: injections.html#steroid).
   전체화면에서: ← → 로 다음 카드, Esc 로 닫기. */
(function () {
  const I = window.INJECTIONS, el = document.getElementById('inj-page');
  if (!I || !el) return;
  const L = I.list || [];
  const ROWS = [['ingredient', '성분'], ['role', '하는 일'], ['onset', '효과'], ['count', '보통 횟수']];
  const li = a => (a || []).map(x => `<li>${x}</li>`).join('');
  const specs = c => ROWS.map(([k, t]) => `<div><dt>${t}</dt><dd>${c[k] || ''}</dd></div>`).join('');

  el.innerHTML = `
    <section class="wrap d-title">
      <h1 class="t-display">${I.title}</h1>
      <p class="t-lead">${I.lead}</p>
    </section>
    <section class="wrap">
      <div class="inj-grid">${L.map((c, i) => `
        <button class="inj-card" type="button" data-i="${i}" aria-haspopup="dialog">
          <span class="n">${String(i + 1).padStart(2, '0')}</span>
          <h2>${c.name}</h2>
          <dl>${specs(c)}</dl>
        </button>`).join('')}
      </div>
    </section>
    <div class="wrap d-body">
      <section class="spec"><h2>주사 맞은 뒤</h2><div><ul class="hl">${li(I.after)}</ul></div></section>
      <section class="spec"><h2>다시 와야 할 때</h2><div><ul class="hl">${li(I.revisit)}</ul></div></section>
      ${I.faq?.length ? `<section class="spec"><h2>질문</h2><div class="faq">${I.faq.map(f => `<details><summary>${f.q}</summary><p>${f.a}</p></details>`).join('')}</div></section>` : ''}
    </div>
    <div class="inj-full" id="inj-full" role="dialog" aria-modal="true" aria-labelledby="inj-full-name" hidden>
      <div class="bar">
        <span class="pos" id="inj-pos"></span>
        <div class="nav">
          <button type="button" class="ic" id="inj-prev" aria-label="이전 주사">‹</button>
          <button type="button" class="ic" id="inj-next" aria-label="다음 주사">›</button>
          <button type="button" class="ic" id="inj-close" aria-label="닫기">×</button>
        </div>
      </div>
      <div class="body wrap">
        <h2 id="inj-full-name"></h2>
        <dl id="inj-full-specs"></dl>
        <p class="note" id="inj-full-note"></p>
        <p class="go" id="inj-full-go"></p>
      </div>
    </div>`;

  const full = document.getElementById('inj-full');
  let cur = -1, opener = null;
  function show(i) {
    cur = (i + L.length) % L.length; const c = L[cur];
    document.getElementById('inj-pos').textContent = `${cur + 1} / ${L.length}`;
    document.getElementById('inj-full-name').textContent = c.name;
    document.getElementById('inj-full-specs').innerHTML = specs(c);
    document.getElementById('inj-full-note').textContent = c.note || '';
    document.getElementById('inj-full-go').innerHTML = (c.models || []).map(m =>
      `<a class="btn ghost small" href="diseases/${m.id}/3d.html#go=${encodeURIComponent(m.go)}">${m.label} 3D에서 보기</a>`).join('');
    if (location.hash !== '#' + c.id) history.replaceState(null, '', '#' + c.id);
  }
  function open(i) {
    opener = document.activeElement; show(i);
    full.hidden = false; document.documentElement.classList.add('inj-lock');
    document.getElementById('inj-close').focus();
  }
  function close() {
    full.hidden = true; document.documentElement.classList.remove('inj-lock');
    history.replaceState(null, '', location.pathname + location.search);
    const b = el.querySelector(`.inj-card[data-i="${cur}"]`); (b || opener)?.focus?.(); cur = -1;
  }
  el.querySelectorAll('.inj-card').forEach(b => b.addEventListener('click', () => open(+b.dataset.i)));
  document.getElementById('inj-prev').onclick = () => show(cur - 1);
  document.getElementById('inj-next').onclick = () => show(cur + 1);
  document.getElementById('inj-close').onclick = close;
  addEventListener('keydown', e => {
    if (full.hidden) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowRight') show(cur + 1);
    else if (e.key === 'ArrowLeft') show(cur - 1);
  });
  // 휴대폰: 좌우로 밀어 넘기기
  let sx = null;
  full.addEventListener('touchstart', e => { sx = e.touches[0].clientX; }, { passive: true });
  full.addEventListener('touchend', e => { if (sx === null) return; const dx = e.changedTouches[0].clientX - sx; sx = null; if (Math.abs(dx) > 60) show(cur + (dx < 0 ? 1 : -1)); });

  const start = L.findIndex(c => '#' + c.id === location.hash);
  if (start >= 0) open(start);
})();
