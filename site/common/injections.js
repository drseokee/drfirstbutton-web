/* 닥터첫단추 — 주사 치료 카드 내용. 이 파일만 고치면 주사 페이지(injections.html)가 바뀝니다.
   카드 1장 = 성분 · 하는 일 · 효과 시기 · 보통 횟수 + 주의 한 줄.
   models: 기존 3D 뷰어에서 주사 장면으로 바로 가는 링크 (go = "단계 이름/하위 단계 이름").

   ※ 모든 문구는 원장님 검토 전 초안입니다. 근거(아래 src 번호)는 이 파일 맨 아래 SOURCES 참고. */
window.INJECTIONS = {
  title: "주사 치료",
  lead: "무슨 주사인지, 언제 듣는지, 몇 번 맞는지.",
  list: [
    {
      id: "steroid", name: "스테로이드 주사",
      ingredient: "트리암시놀론 등 스테로이드 + 국소마취제",
      role: "염증을 강하게 가라앉힙니다",
      onset: "2~7일 뒤부터, 수주~수개월",
      count: "6개월에 3회 이내가 원칙. 증상에 따라 조절",
      note: "당뇨가 있으면 며칠 혈당이 오를 수 있어요. 이틀은 탕 목욕을 피하고 샤워는 괜찮아요.",
      models: [
        { id: "carpal-tunnel", label: "손목", go: "치료/국소 주사" },
        { id: "knee-oa", label: "무릎", go: "치료/관절 주사" },
        { id: "rotator-cuff", label: "어깨", go: "치료/주사" }
      ],
      src: [1, 5, 9]
    },
    {
      id: "hyaluronic", name: "히알루론산 주사",
      ingredient: "히알루론산 (관절액에 원래 있는 성분)",
      role: "관절 안을 미끄럽게 하고 충격을 줄입니다",
      onset: "몇 주 뒤부터, 수개월",
      count: "제품에 따라 1~5회. 보통 6개월 뒤 다시 맞을 수 있음",
      note: "주사 후 이틀은 달리기·무거운 물건 들기를 피하세요.",
      models: [{ id: "knee-oa", label: "무릎", go: "치료/관절 주사" }],
      src: [2]
    },
    {
      id: "pn", name: "PN 주사",
      ingredient: "폴리뉴클레오티드 (연어 DNA에서 정제)",
      role: "관절 안을 부드럽게 하고 조직 회복을 돕습니다",
      onset: "2주쯤부터",
      count: "1주 간격 3회",
      note: "연어·생선 알레르기가 있으면 미리 알려 주세요.",
      models: [{ id: "knee-oa", label: "무릎", go: "치료/관절 주사" }],
      src: [3]
    },
    {
      id: "prolo", name: "증식 치료 (프롤로)",
      ingredient: "고농도 포도당",
      role: "약해진 인대·힘줄 부착부에 회복 반응을 일으킵니다",
      onset: "여러 번 맞으며 서서히",
      count: "4주 간격 3~5회",
      note: "주사 후 며칠은 뻐근하고 더 아플 수 있어요.",
      src: [4]
    },
    {
      id: "nerve-block", name: "신경 차단술",
      ingredient: "국소마취제 + 스테로이드",
      role: "눌린 신경 주변의 염증과 통증을 줄입니다",
      onset: "2~7일 뒤부터, 수주~수개월",
      count: "1회 후 경과 보고 결정. 1년에 2~3회 이내",
      note: "당일은 운전을 피하세요. 다리가 잠시 저리거나 힘이 빠질 수 있어요.",
      src: [6]
    },
    {
      id: "prp", name: "PRP 주사",
      ingredient: "내 혈액에서 모은 혈소판",
      role: "혈소판의 성장인자로 힘줄·관절 회복을 자극합니다",
      onset: "몇 주 뒤부터, 수개월에 걸쳐",
      count: "1~3회. 부위와 상태에 따라 다름",
      note: "주사 후 며칠은 붓고 뻐근할 수 있어요.",
      src: [7]
    },
    {
      id: "local", name: "국소마취 주사",
      ingredient: "리도카인 등 국소마취제",
      role: "통증 신호를 잠시 끊습니다. 아픈 곳을 찾을 때도 씁니다",
      onset: "몇 분 안에, 몇 시간",
      count: "검사·시술 때 1회",
      note: "마취가 풀리면 원래 통증이 돌아오는 것이 정상이에요.",
      src: [8]
    }
  ],
  // 카드 아래 공통 안내
  after: [
    "주사 맞은 곳은 하루이틀 아껴 쓰세요.",
    "아프면 얼음찜질은 괜찮고, 온찜질은 피하세요.",
    "주사는 통증을 줄여 운동·재활을 할 수 있게 돕는 치료입니다."
  ],
  revisit: [
    "주사 부위가 점점 더 아프고 붉어질 때",
    "붓기가 이틀 넘게 계속될 때",
    "열이 날 때"
  ],
  faq: [
    { q: "스테로이드 주사는 뼈를 상하게 하나요?", a: "간격을 두고 가끔 맞는 주사는 대체로 안전합니다. 같은 곳에 짧은 간격으로 여러 번 맞으면 연골·힘줄이 약해질 수 있어서, 횟수와 간격을 정해 두고 맞습니다." },
    { q: "몇 번 맞아야 낫나요?", a: "주사마다 정해진 횟수가 있지만, 낫는 것은 주사만이 아니라 운동·자세·체중 관리가 함께 할 때입니다. 효과가 없으면 횟수를 채우기보다 다른 치료를 상의합니다." },
    { q: "주사 맞고 더 아파요.", a: "스테로이드 주사는 하루이틀 더 아플 수 있고, 증식 치료·PRP는 며칠 뻐근한 것이 흔합니다. 점점 심해지거나 붉고 뜨거우면 바로 오세요." }
  ]
};

/* 근거 (검토용, 화면에는 표시하지 않음)
   1. Mayo Clinic, Cortisone shots (2026.3)  https://www.mayoclinic.org/tests-procedures/cortisone-shots/about/pac-20384794
      — 하루이틀 통증 악화 가능, 효과 수개월, 연간 횟수 제한, 당뇨 혈당 일시 상승, 이틀 탕 목욕 금지·샤워 가능, 온찜질 금지, 48시간 넘는 붓기·발적은 감염 신호
   2. AAOS OrthoInfo, Viscosupplementation Treatment for Knee Arthritis  https://orthoinfo.aaos.org/en/treatment/viscosupplementation-treatment-for-knee-arthritis
      — 제품에 따라 1~5회, 효과까지 수주, 수개월 지속, 보통 6개월 뒤 반복, 48시간 과격한 활동 피하기 (AAOS는 효과가 불분명하다고 기술)
   3. Kim et al., Sci Rep 2023;13:9419 (PN vs 고분자 HA 무작위 대조)  https://pmc.ncbi.nlm.nih.gov/articles/PMC10256705/
      — 콘쥬란 1주 간격 3회, 2주부터 호전, 16주에 HA와 비슷한 효과
   4. Rabago et al., Ann Fam Med 2013;11:229 (무릎 덱스트로스 프롤로)  https://www.annfammed.org/content/11/3/229
      — 1·5·9주 주사(선택 13·17주), 평균 3.95회, 52주 WOMAC 개선
   5. Cleveland Clinic, Epidural Steroid Injection  https://my.clevelandclinic.org/health/treatments/22301-epidural-steroid-injection-esi
      — 스테로이드 효과 2~7일 뒤 시작 (스테로이드 카드 효과 시기 근거로도 씀)
   6. 위와 같음 — 수주~수개월, 대부분 1년 2~3회로 제한, 스테로이드 ± 국소마취제
   7. Cleveland Clinic, PRP Injection (2024.12)  https://my.clevelandclinic.org/health/treatments/platelet-rich-plasma-prp-injection
      — 수주 뒤 효과, 여러 번 필요할 수 있음 (횟수 1~3회는 출처 미확인 초안)
   9. 원장님 기준 (2026-11-26): 스테로이드 6개월에 3회 이내 원칙, 증상 정도에 따라 조절
   ※ PRP 횟수·신경 차단술/PN 주의 문구는 원장님이 초안대로 승인 (2026-11-26). 급여/비급여는 화면에 표시하지 않음.
   8. 출처 미확인 — 국소마취제 일반 약리(리도카인 수분 내 작용, 1~2시간 지속)
*/
