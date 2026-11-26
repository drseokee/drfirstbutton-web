# pipeline — 제작 스크립트와 팩 데이터

새 세션에서 이어서 작업하려면:
1. `pip install bpy --break-system-packages` (Blender 5.x 파이썬 모듈), `git clone --depth 1 https://github.com/Z-Anatomy/Z-Anatomy` (Startup.blend)
2. `pipeline/common/zana.py`(도우미), `bake_ao.py`(AO), `qa.py`(관통 검사 게이트)
3. 손목터널: `carpal-tunnel/` — extract → step5a → step5b → step5c → step6 → qa → viewer6_template.html에 model.json을 `__DATA__`로 인라인
4. 발목 염좌: `ankle-sprain/` — ankle_a → ankle_b → bake_ao → viewer_ankle_template.html + model.json
5. 요추 압박골절: `compression-fracture/` — spine_a → spine_b → viewer_spine_template.html + model.json (L3 골절, 뷰어 하나). `viewer_spine_b_template.html`은 예전 L2 확인용 시안이라 지금 model.json으로는 열리지 않는다.
6. 팩들의 `model.json`은 이미 계산된 최종 데이터라, Blender 없이 뷰어 수정만 할 때는 이것만 있으면 된다.
