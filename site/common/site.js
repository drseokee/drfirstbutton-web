/* 닥터첫단추 — 공통 레이아웃. 모든 페이지가 이 파일을 불러 씁니다.
   header/footer 삽입, 질환 카드 목록, 질환 페이지 채우기.  데이터는 common/data.js 와 diseases/<id>/info.js 에 있습니다. */
(function () {
  const SITE = window.SITE || {};
  const root = (document.body.dataset.root || '.').replace(/\/$/, '');   // 페이지 위치에 따른 상대 경로 접두어

  // ---------- header ----------
  const header = document.createElement('header');
  header.className = 'site-header';
  header.innerHTML = `<div class="wrap">
      <a class="brand" href="${root}/index.html"><span class="btn-mark"></span>${SITE.brand || '닥터첫단추'}</a>
      <nav class="site-nav">
        <a href="${root}/index.html#about">소개</a>
        <a href="${root}/index.html#diseases">질환별 3D 설명</a>
        ${(SITE.links || []).map(l => `<a href="${l.url}" target="_blank" rel="noopener">${l.label}</a>`).join('')}
      </nav></div>`;
  document.body.prepend(header);

  // ---------- footer ----------
  const footer = document.createElement('footer');
  footer.className = 'site-footer';
  footer.innerHTML = `<div class="wrap">
      <div class="brand"><span class="btn-mark"></span>${SITE.brand || '닥터첫단추'}</div>
      <p class="notice">${SITE.disclaimer || ''}</p>
      <p>${SITE.attribution || ''}</p>
      <p>© ${new Date().getFullYear()} ${SITE.brand || '닥터첫단추'}</p></div>`;
  document.body.append(footer);

  // ---------- disease cards (index) ----------
  const cardsEl = document.getElementById('disease-cards');
  if (cardsEl) {
    cardsEl.innerHTML = (SITE.diseases || []).map(d => d.ready
      ? `<a class="card" href="${root}/disease.html?id=${d.id}">
           <div class="thumb" style="background-image:url('${root}/diseases/${d.id}/${d.thumb || 'thumb.jpg'}')"></div>
           <div class="body"><h3>${d.title}</h3><p class="sub">${d.summary}</p>
             <div class="tags">${(d.tags || []).map(t => `<span class="tag">${t}</span>`).join('')}</div></div></a>`
      : `<div class="card soon"><div class="thumb"></div>
           <div class="body"><h3>${d.title}</h3><p class="sub">${d.summary || '준비 중'}</p>
             <div class="tags"><span class="tag">준비 중</span></div></div></div>`).join('');
  }

  // ---------- disease page ----------
  const page = document.getElementById('disease-page');
  if (page) {
    const id = new URLSearchParams(location.search).get('id') || (SITE.diseases || []).find(d => d.ready)?.id;
    const s = document.createElement('script');
    s.src = `${root}/diseases/${id}/info.js`;
    s.onload = () => {
      const D = window.DISEASE_INFO; if (!D) return;
      document.title = `${D.title} — ${SITE.brand || '닥터첫단추'}`;
      const li = arr => (arr || []).map(x => `<li>${x}</li>`).join('');
      page.innerHTML = `
        <section class="disease-hero wrap">
          <div><div class="eyebrow">${D.category || '정형외과'}</div><h1>${D.title}</h1><p class="lead">${D.lead}</p></div>
          <a class="btn primary" href="${root}/diseases/${id}/3d.html">3D로 보기 →</a>
        </section>
        <section class="wrap disease-grid">
          <div class="block"><h3>이런 증상이 있어요</h3><ul>${li(D.symptoms)}</ul></div>
          <div class="block"><h3>왜 생기나요</h3><ul>${li(D.causes)}</ul></div>
          <div class="block"><h3>어떻게 치료하나요</h3><ul>${li(D.treatments)}</ul></div>
        </section>
        <section class="wrap"><div class="viewer-cta">
          <div><h3>손목을 열어 직접 보기</h3><p>${D.viewerBlurb || '회전·확대하며 단계별로 설명을 따라갈 수 있는 3D 교육 자료입니다.'}</p></div>
          <a class="btn primary" href="${root}/diseases/${id}/3d.html">3D 설명 열기</a>
        </div></section>`;
    };
    s.onerror = () => { page.innerHTML = `<section class="wrap" style="padding-top:140px"><h1>준비 중인 질환입니다</h1></section>`; };
    document.head.append(s);
  }
})();
