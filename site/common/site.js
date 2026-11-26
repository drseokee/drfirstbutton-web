/* 닥터첫단추 — 공통 레이아웃. 모든 페이지가 이 파일을 불러 씁니다.
   header/footer 삽입, 질환 목록, 소개·영상 채우기, 질환 페이지 채우기.
   데이터는 common/data.js 와 diseases/<id>/info.js 에 있습니다. */
(function () {
  const SITE = window.SITE || {};
  const root = (document.body.dataset.root || '.').replace(/\/$/, '');   // 페이지 위치에 따른 상대 경로 접두어
  const page = document.body.dataset.page || '';                          // index | disease
  const brand = SITE.brand || '닥터첫단추';
  // 로고: 기존 일러스트(금색 첫 단추를 끼우는 의사)에서 손과 단추만 잘라 원형으로. 원본은 docs/brand/.
  const MARK = `<img class="mark" src="${root}/common/brand/mark-96.jpg" width="32" height="32" alt="">`;
  const isPh = s => typeof s === 'string' && /^\[.*\]$/.test(s.trim());   // "[이름]" 같은 자리표시자
  const txt = s => isPh(s) ? `<span class="ph">${s}</span>` : (s || '');
  const realLinks = (SITE.links || []).filter(l => l.url && !isPh(l.url));
  const ext = l => `<a href="${l.url}" target="_blank" rel="noopener">${l.label}</a>`;

  // ---------- header ----------
  const header = document.createElement('header');
  header.className = 'site-header';
  header.innerHTML = `<div class="wrap">
      <a class="brand" href="${root}/index.html">${MARK}${brand}</a>
      <nav class="site-nav" aria-label="주요 메뉴">
        <a href="${root}/index.html#diseases"${page === 'disease' ? ' aria-current="page"' : ''}>질환 3D</a>
        <a href="${root}/index.html#about">소개</a>
        ${realLinks.map(l => ext(l).replace('<a ', '<a class="opt" ')).join('')}
      </nav></div>`;
  document.body.prepend(header);

  // ---------- footer ----------
  const footer = document.createElement('footer');
  footer.className = 'site-footer';
  footer.innerHTML = `<div class="wrap">
      <div class="top"><span class="brand">${brand}</span>
        <nav aria-label="바닥 메뉴"><a href="${root}/index.html#diseases">질환 3D</a><a href="${root}/index.html#about">소개</a>${realLinks.map(ext).join('')}</nav></div>
      <p class="notice">${SITE.disclaimer || ''}</p>
      <p>${SITE.attribution || ''} · © ${new Date().getFullYear()} ${brand}</p></div>`;
  document.body.append(footer);

  const ready = (SITE.diseases || []).filter(d => d.ready);

  const tile = d => `<a class="tile" href="${root}/disease.html?id=${d.id}">
      <div class="tile-t"><h3>${d.title}</h3><p>${(d.tags || []).join(' · ')}</p></div>
      <img src="${root}/diseases/${d.id}/stage.jpg" alt="" loading="lazy" onerror="this.src='${root}/diseases/${d.id}/${d.thumb || 'thumb.jpg'}'"></a>`;

  // ---------- 질환 (index) : 정렬된 이미지 격자 + 준비 중 한 줄 ----------
  const listEl = document.getElementById('disease-list');
  if (listEl) {
    listEl.innerHTML = ready.map(tile).join('');
    const soon = (SITE.diseases || []).filter(d => !d.ready).map(d => d.title);
    const soonEl = document.getElementById('disease-soon');
    if (soonEl) soonEl.textContent = soon.length ? `준비 중 · ${soon.join(' · ')}` : '';
  }

  // ---------- 소개 (index) : 이름 · 한 문장 · 채널 ----------
  const about = document.getElementById('about-body');
  if (about) {
    const P = SITE.person || {};
    document.getElementById('about-photo').innerHTML = P.photo ? `<img src="${root}/${P.photo}" alt="${P.name}">` : '<span>[프로필 사진]</span>';
    about.innerHTML = `
      <p class="kicker">${P.role || ''} ${txt(P.name)}</p>
      <p class="quote">${txt(P.quote || SITE.tagline || '')}</p>
      <p class="links">${(SITE.links || []).map(l => isPh(l.url) ? `<span class="ph">${l.label}</span>` : `<a class="more" href="${l.url}" target="_blank" rel="noopener">${l.label}</a>`).join('')}</p>`;
  }

  // ---------- 유튜브 (index) : data.js의 videos가 있을 때만 영상 목록 ----------
  const vids = document.getElementById('videos');
  if (vids) {
    const yt = (SITE.links || []).find(l => /유튜브|youtube/i.test(l.label));
    const ch = document.getElementById('yt-channel');
    if (ch) { if (yt && !isPh(yt.url)) ch.href = yt.url; else ch.remove(); }
    const V = (SITE.videos || []).filter(v => v.id);
    if (V.length) vids.innerHTML = V.slice(0, 3).map(v => `
      <a class="video" href="https://www.youtube.com/watch?v=${v.id}" target="_blank" rel="noopener">
        <div class="ratio"><img src="https://i.ytimg.com/vi/${v.id}/hqdefault.jpg" alt="" loading="lazy"></div>
        <p>${v.title}</p>${v.meta ? `<small>${v.meta}</small>` : ''}</a>`).join('');
    else document.getElementById('youtube')?.remove();
  }

  // ---------- 질환 페이지 ----------
  const dpage = document.getElementById('disease-page');
  if (dpage) {
    const id = new URLSearchParams(location.search).get('id') || ready[0]?.id;
    const meta = (SITE.diseases || []).find(d => d.id === id) || {};
    const s = document.createElement('script');
    s.src = `${root}/diseases/${id}/info.js`;
    s.onload = () => {
      const D = window.DISEASE_INFO; if (!D) return;
      document.title = `${D.title} — ${brand}`;
      const base = `${root}/diseases/${id}`;
      const v3d = `${base}/3d.html`;
      const li = arr => (arr || []).map(x => `<li>${x}</li>`).join('');
      const row = (h, body) => `<section class="spec"><h2>${h}</h2><div>${body}</div></section>`;
      const secs = [
        D.symptoms?.length && row('증상', `<ul class="hl">${li(D.symptoms)}</ul>`),
        D.causes?.length && row('원인', `<ul class="hl">${li(D.causes)}</ul>`),
        D.treatments?.length && row('치료', `<ul class="hl">${li(D.treatments)}</ul>`),
        D.redFlags?.length && row('바로 병원에', `<ul class="hl">${li(D.redFlags)}</ul>`),
        D.faq?.length && row('질문', `<div class="faq">${D.faq.map(f => `<details><summary>${f.q}</summary><p>${f.a}</p></details>`).join('')}</div>`),
      ].filter(Boolean);
      const others = ready.filter(d => d.id !== id);

      dpage.innerHTML = `
        <section class="wrap d-title">
          <h1 class="t-display">${D.title}</h1>
          <p class="t-lead">${D.lead}</p>
        </section>
        <section class="wrap d-stage">
          <a class="frame" href="${v3d}" aria-label="${D.title} 3D 설명 열기">
            <div class="media"><img src="${base}/${D.stageImage || 'stage.jpg'}" alt="${D.title} 3D 모형" onerror="this.src='${base}/${meta.thumb || 'thumb.jpg'}'">
              <span class="btn light small">3D 보기</span></div>
            ${D.stages?.length ? `<div class="steps">${D.stages.map((n, i) => `<span><b>${i + 1}</b>${n}</span>`).join('')}</div>` : ''}
          </a>
        </section>
        <div class="wrap d-body">${secs.join('')}</div>
        ${others.length ? `<section class="wrap next"><h2 class="t-2">다른 질환</h2><div class="tiles small">${others.map(tile).join('')}</div></section>` : ''}`;
      reveal(dpage.querySelectorAll('.spec, .next .tile'));
    };
    s.onerror = () => { dpage.innerHTML = `<section class="wrap d-title"><h1 class="t-1">준비 중인 질환입니다</h1><p class="t-lead"><a class="more" href="${root}/index.html#diseases">질환 목록으로</a></p></section>`; };
    document.head.append(s);
  }

  // ---------- 등장 효과: 화면에 들어올 때 한 번만 ----------
  function reveal(nodes) {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { rootMargin: '0px 0px -8% 0px' });
    nodes.forEach(n => { if (n.getBoundingClientRect().top > innerHeight) { n.classList.add('reveal'); io.observe(n); } });
  }
  reveal(document.querySelectorAll('.head-c, .tiles .tile, .about > *, .videos > *'));
})();
