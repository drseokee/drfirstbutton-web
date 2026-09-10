# pipeline — 제작 스크립트와 팩 데이터

새 세션에서 이어서 작업하려면:
1. `pip install bpy --break-system-packages` (Blender 5.x 파이썬 모듈), `git clone --depth 1 https://github.com/Z-Anatomy/Z-Anatomy` (Startup.blend)
2. `pipeline/common/zana.py`(도우미), `bake_ao.py`(AO), `qa.py`(관통 검사 게이트)
3. 손목터널: `carpal-tunnel/` — extract → step5a → step5b → step5c → step6 → qa → viewer6_template.html에 model.json을 `__DATA__`로 인라인
4. 발목 염좌: `ankle-sprain/` — ankle_a → ankle_b → bake_ao → viewer_ankle_template.html + model.json
5. 두 팩의 `model.json`은 이미 계산된 최종 데이터라, Blender 없이 뷰어 수정만 할 때는 이것만 있으면 된다.
