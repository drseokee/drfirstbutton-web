# pipeline — 제작 스크립트와 팩 데이터

새 세션에서 이어서 작업하려면:
1. `pip install bpy --break-system-packages` (Blender 5.x 파이썬 모듈), `git clone --depth 1 https://github.com/Z-Anatomy/Z-Anatomy` (Startup.blend)
2. `pipeline/common/zana.py`(도우미), `bake_ao.py`(AO), `qa.py`(관통 검사 게이트)
3. 손목터널: `carpal-tunnel/` — extract → step5a → step5b → step5c → step6 → qa → viewer6_template.html에 model.json을 `__DATA__`로 인라인
4. 발목 염좌: `ankle-sprain/` — ankle_a → ankle_b → bake_ao → viewer_ankle_template.html + model.json
5. 두 팩의 `model.json`은 이미 계산된 최종 데이터라, Blender 없이 뷰어 수정만 할 때는 이것만 있으면 된다.
6. 요추 압박골절: `compression-fracture/` — spine_a → spine_b → viewer_spine_template.html + model.json (`__DATA__` 자리에 model.json 그대로) → `site/diseases/compression-fracture/3d.html`. `viewer_spine_b_template.html`은 리그 확인용(배포 안 함).
7. 어깨 회전근개: `rotator-cuff/` — 원본은 `LluisV/Z-Anatomy` 저장소의 FBX(`Resources/Models/FBX/`, 클라우드에서 `Z-Anatomy/Z-Anatomy`는 받을 수 없음). `import_fbx.py`(FBX → za_all.blend, 부모 변환 적용) → `shoulder_a.py`(추출·팔꿈치 90° 굽힘·리그 가중치·극상근 병리 속성) → `common/bake_ao.py` → `build.py`(템플릿 + model.json → `site/diseases/rotator-cuff/3d.html`). 뷰어 템플릿은 `viewer_shoulder_template.html`(직접 고칠 때는 이 파일을 고치고 `__DATA__`에 model.json 치환).
8. 근육·힘줄의 관절 통과 변형: `site/common/muscle-fibres.js`(공용). 관절을 건너는 구간만 뼈→뼈 직선 섬유로 늘고 줄며, 관절 중심 구에 감겨 뼈를 뚫지 않는다(어깨 PR #9 방식의 일반형). 발목(거골 감싸기)·손(손가락 관절 감싸기) 뷰어가 사용. 뷰어 주소에 `?oldmuscle`을 붙이면 이전 피부 가중치 방식으로 비교.
9. 템플릿 → 배포 파일: `python3 pipeline/common/build_viewer.py ankle-sprain carpal-tunnel` (model.json을 `__DATA__`에 인라인해 `site/diseases/<주제>/3d.html` 생성).
