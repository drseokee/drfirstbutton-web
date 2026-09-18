/* 닥터첫단추 — 사이트 데이터. 이름·소개·링크·질환 목록은 여기서만 고칩니다. */
window.SITE = {
  brand: "닥터첫단추",
  tagline: "첫 단추를 잘 끼우면, 치료가 쉬워집니다.",
  // ---- 소개 (자리표시자: 실제 문구로 교체해 주세요) ----
  person: {
    name: "[이름]",
    role: "정형외과 전문의",
    bio: [
      "[소개문 1 — 예: 손·손목·어깨 질환을 주로 진료하는 정형외과 전문의입니다.]",
      "[소개문 2 — 예: 환자가 자기 몸에서 무슨 일이 일어나는지 이해할 때 치료가 쉬워진다고 믿습니다.]",
      "[소개문 3 — 예: 그래서 진료실에서 쓰는 3D 설명 자료를 직접 만들어 공유합니다.]"
    ],
    photo: ""          // 예: "common/profile.jpg" (없으면 비워 두기)
  },
  links: [
    { label: "블로그", url: "https://blog.naver.com/drfirstbutton" },
    { label: "유튜브", url: "[유튜브 주소]" }
  ],
  // ---- 질환 목록: 폴더 이름 = id ----
  diseases: [
    { id: "carpal-tunnel", ready: true, title: "손목터널증후군", summary: "손이 저리고 아픈 이유를 손목 안에서 직접 봅니다.", tags: ["손·손목", "신경"], thumb: "thumb.jpg" },
    { id: "ankle-sprain", ready: true, title: "발목 염좌", summary: "발을 삐었을 때 바깥쪽 인대에 무슨 일이 생기는지 직접 꺾어 봅니다.", tags: ["발·발목", "인대"], thumb: "thumb.jpg" },
    { id: "knee-oa", ready: true, title: "무릎 골관절염", summary: "연골이 닳아 뼈끼리 닿기까지, 무릎 안에서 무슨 일이 생기는지 봅니다.", tags: ["무릎", "연골"], thumb: "thumb.jpg" },
    { id: "trigger-finger", ready: false, title: "방아쇠수지", summary: "손가락이 걸리고 튕기는 이유" },
    { id: "distal-radius-fracture", ready: false, title: "손목 골절과 뼈가 붙는 과정", summary: "골절 → 고정 → 골유합" }
  ],
  disclaimer: "이 사이트의 3D 모형과 설명은 일반적인 의학 정보를 쉽게 이해하도록 돕기 위한 교육 자료입니다. 개인의 진단·치료를 대신하지 않으며, 증상이 있으면 의료진과 상담하세요.",
  attribution: "3D 모형: Z-Anatomy (CC BY-SA 4.0) · BodyParts3D (CC BY-SA 2.1 JP) 기반 제작 · 힘줄·인대 일부는 도식화"
};
