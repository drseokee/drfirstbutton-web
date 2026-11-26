/* 닥터첫단추 — 공통 레이아웃. 모든 페이지가 이 파일을 불러 씁니다.
   header/footer 삽입, 질환 목록, 소개·영상 채우기, 질환 페이지 채우기.
   데이터는 common/data.js 와 diseases/<id>/info.js 에 있습니다. */
(function () {
  const SITE = window.SITE || {};
  const root = (document.body.dataset.root || '.').replace(/\/$/, '');   // 페이지 위치에 따른 상대 경로 접두어
  const page = document.body.dataset.page || '';                          // index | disease
  const brand = SITE.brand || '닥터첫단추';
  // 로고: 흰 가운 실루엣 + 금색 첫 단추 (docs/brand/). 가운은 글자색을 따르고, 단추만 금색.
  const MARK = `<svg width="22" height="22" viewBox="0 0 64 64" aria-hidden="true"><path fill="currentColor" d="M6 12Q6 6 12 6H21L32 31L43 6H52Q58 6 58 12V58H6Z"/><circle cx="32" cy="35" r="7" fill="#B08A3E"/></svg>`;
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

  const pad2 = n => String(n).padStart(2, '0');
  const ready = (SITE.diseases || []).filter(d => d.ready);

  // ---------- 질환 목록 (index) ----------
  const listEl = document.getElementById('disease-list');
  if (listEl) {
    listEl.innerHTML = (SITE.diseases || []).map((d, i) => d.ready
      ? `<a class="row" href="${root}/disease.html?id=${d.id}">
           <span class="num">${pad2(i + 1)}</span>
           <div><h3>${d.title}</h3><p class="sub">${d.summary}</p></div>
           <div class="side"><span class="tags">${(d.tags || []).join(' · ')}</span>
             <img class="thumb" src="${root}/diseases/${d.id}/${d.thumb || 'thumb.jpg'}" alt="" loading="lazy"></div></a>`
      : `<div class="row soon"><span class="num">${pad2(i + 1)}</span><h3>${d.title}</h3><span class="tags">준비 중</span></div>`).join('');
  }

  // ---------- 소개 (index) ----------
  const about = document.getElementById('about-body');
  if (about) {
    const P = SITE.person || {};
    document.getElementById('about-photo').innerHTML = P.photo ? `<img src="${root}/${P.photo}" alt="${P.name}">` : '<span>[프로필 사진]</span>';
    about.innerHTML = `
      <p class="kicker">${P.role || ''} ${txt(P.name)}</p>
      <p class="quote">${txt(P.quote || SITE.tagline || '')}</p>
      <div class="bio">${(P.bio || []).map(t => `<p>${txt(t)}</p>`).join('')}</div>
      <dl class="facts">
        ${(P.facts || []).map(f => `<dt>${f.label}</dt><dd>${txt(f.value)}</dd>`).join('')}
        <dt>채널</dt><dd>${(SITE.links || []).map(l => isPh(l.url) ? `<span class="ph">${l.label}</span>` : `<a class="u" href="${l.url}" target="_blank" rel="noopener">${l.label}</a>`).join(' · ')}</dd>
      </dl>`;
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
      const secs = [
        D.symptoms?.length && { id: 's-sym', name: '증상', html: `<h2 class="t-2">이런 증상이 있어요</h2><ol class="nlist">${li(D.symptoms)}</ol>` },
        D.causes?.length && { id: 's-cause', name: '왜 생기나요', html: `<h2 class="t-2">왜 생기나요</h2><ol class="nlist">${li(D.causes)}</ol>` },
        D.treatments?.length && { id: 's-tx', name: '치료', html: `<h2 class="t-2">어떻게 치료하나요</h2><ol class="nlist">${li(D.treatments)}</ol>` },
        D.redFlags?.length && { id: 's-flag', name: '이럴 땐 바로 병원에', html: `<div class="callout"><h2>이럴 땐 미루지 말고 진료를 받으세요</h2><ul>${li(D.redFlags)}</ul></div>` },
        D.faq?.length && { id: 's-faq', name: '자주 묻는 질문', html: `<h2 class="t-2">자주 묻는 질문</h2><div class="faq">${D.faq.map((f, i) => `<details${i ? '' : ' open'}><summary>${f.q}</summary><p>${f.a}</p></details>`).join('')}</div>` },
      ].filter(Boolean);
      const others = ready.filter(d => d.id !== id);
      const tags = meta.tags || (D.category || '').split('·').map(x => x.trim());

      dpage.innerHTML = `
        <section class="wrap d-title">
          <p class="crumb"><a href="${root}/index.html#diseases">질환 3D</a><i aria-hidden="true">/</i>${tags[0] || '정형외과'}</p>
          <h1 class="t-display">${D.title}</h1>
          <p class="t-lead">${D.lead}</p>
          <dl class="d-meta">
            <div><dt>부위</dt><dd>${tags[0] || ''}</dd></div>
            ${tags[1] ? `<div><dt>관련 구조</dt><dd>${tags.slice(1).join(' · ')}</dd></div>` : ''}
            ${D.stages?.length ? `<div><dt>3D 설명</dt><dd>${D.stages.length}단계</dd></div>` : ''}
          </dl>
        </section>
        <section class="wrap d-stage">
          <a class="frame" href="${v3d}" aria-label="${D.title} 3D 설명 열기">
            <div class="media"><img src="${base}/${D.stageImage || 'stage.jpg'}" alt="${D.title} 3D 모형" onerror="this.src='${base}/${meta.thumb || 'thumb.jpg'}'">
              <span class="btn light small">3D로 직접 돌려보기</span></div>
            ${D.stages?.length ? `<div class="steps">${D.stages.map((n, i) => `<span><b>${i + 1}</b>${n}</span>`).join('')}</div>` : ''}
          </a>
          ${D.viewerBlurb ? `<p class="note">${D.viewerBlurb}</p>` : ''}
        </section>
        <div class="wrap d-body">
          <nav class="toc" aria-label="이 페이지 목차"><p>이 페이지</p>${secs.map(x => `<a href="#${x.id}">${x.name}</a>`).join('')}</nav>
          <article class="article">${secs.map(x => `<section id="${x.id}">${x.html}</section>`).join('')}</article>
        </div>
        ${others.length ? `<section class="next"><div class="wrap"><p class="kicker">다른 질환도 열어 보기</p><div class="grid">
          ${others.map(o => `<a href="${root}/disease.html?id=${o.id}"><img src="${root}/diseases/${o.id}/${o.thumb || 'thumb.jpg'}" alt="" loading="lazy"><span><b>${o.title}</b><small>${(o.tags || []).join(' · ')}</small></span></a>`).join('')}
        </div></div></section>` : ''}`;

      // 목차: 지금 읽는 구역 표시
      const links = [...dpage.querySelectorAll('.toc a')];
      const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) links.forEach(a => a.classList.toggle('on', a.hash === '#' + e.target.id)); }), { rootMargin: '-30% 0px -60% 0px' });
      dpage.querySelectorAll('.article > section').forEach(x => io.observe(x));
      reveal(dpage.querySelectorAll('.article > section, .next .grid > a'));
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
  reveal(document.querySelectorAll('.sec-head, .dlist .row, .about > *, .videos > *'));
})();
