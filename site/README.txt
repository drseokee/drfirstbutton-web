닥터첫단추 사이트 폴더 — 올릴 때는 이 폴더 전체를 그대로 올립니다.

바꿀 때 어디를 고치나
- 이름·소개문·링크·질환 목록 ......... common/data.js
- 색·글꼴·버튼 모양 (전 페이지 일괄) ... common/style.css
- 질환 페이지 내용 ................... diseases/<질환>/info.js
- 질환 3D 뷰어 ....................... diseases/<질환>/3d.html  (파이프라인 산출물, 손으로 고치지 않음)
- 질환 카드 썸네일 ................... diseases/<질환>/thumb.jpg (720x420)

새 질환 추가
1) diseases/ 아래 폴더 하나 (예: trigger-finger) 에 info.js, 3d.html, thumb.jpg
2) common/data.js 의 diseases 목록에 { id: "trigger-finger", ready: true, ... } 한 줄
