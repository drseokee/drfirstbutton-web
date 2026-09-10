# 닥터첫단추 — 환자 교육 웹사이트

정형외과 질환을 3D로 열어 보는 환자 교육 사이트. 서버 없는 정적 사이트이며 `site/` 폴더가 그대로 배포됩니다.

## 구조
- `site/index.html` — 메인 (스크롤 구동 3D 손 + 소개 + 질환 카드)
- `site/disease.html?id=<질환>` — 질환 페이지 (양식 하나, 내용은 질환 팩에서)
- `site/common/` — 공통 스타일(style.css)·레이아웃(site.js)·사이트 데이터(data.js)
- `site/diseases/<질환>/` — 질환 팩: info.js(내용), 3d.html(3D 뷰어), thumb.jpg(썸네일)
- `wrangler.jsonc` — Cloudflare 배포 설정

## 갱신
이 저장소에 파일이 올라가면 Cloudflare가 자동으로 배포합니다.

## 저작자 표시
3D 모형은 Z-Anatomy (CC BY-SA 4.0) · BodyParts3D (CC BY-SA 2.1 JP)에서 파생되었으며, 같은 조건으로 공개합니다. 교육용 자료이며 개인의 진단·치료를 대신하지 않습니다.
