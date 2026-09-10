# 환자 설명용 3D 모델 제작 규칙 (CONVENTIONS)

웹 뷰어는 주제를 모른다. glTF 노드 이름과 `stages.json`만 읽는다.
이 규칙을 지키면 새 주제(골절·골유합·수술)를 추가해도 뷰어 코드는 손대지 않는다.

## 0. 도구
- Blender **4.5 LTS** (2027-07까지 지원). 지오메트리 출처: Z-Anatomy(CC BY-SA 4.0) / CT→TotalSegmentator(뼈 형태가 중요한 주제)
- export: glTF 2.0 (.glb), 카메라·애니메이션·shape key 포함

## 1. 오브젝트 이름 = `층__구조[__변형]`
Blender 오브젝트명이 glTF 노드명으로 그대로 나간다. 뷰어는 **접두사**로 층을 판별한다(컬렉션 계층에 의존하지 않음).

| 층 | 예 |
|---|---|
| skin | `skin__hand` |
| bone | `bone__scaphoid`, `bone__radius_distal`, `bone__mc3` |
| lig | `lig__tcl` |
| tendon | `tendon__fds_2` … `tendon__fpl` |
| nerve | `nerve__median` |
| prop | `prop__syringe` |
| cam | `cam__1` … `cam__5` (Blender 카메라 오브젝트) |

변형 접미사(`__변형`)는 스테이지에서 **통째로 스왑**되는 세트를 뜻한다.
- `__cut` : 단면 변형 (손목터널: 유구골 갈고리 레벨). 스테이지 2부터 full 세트 숨기고 `__cut` 세트 표시
- `__released_radial` / `__released_ulnar` : 인대 절개 후 두 조각
- 골절 주제 예: `bone__radius__fx`, `bone__radius__callus`, `bone__radius__union`

Blender 컬렉션은 층 이름(skin / bone / lig / tendon / nerve / prop / cam)으로 정리한다.

## 2. 변화 표현
- **형태 변화 = shape key** → glTF morph target. 이름 그대로 export됨.
  - `lig__tcl` : `thick`
  - `nerve__median` : `compressed`
  - Basis 대비 상대 키만 사용. **모디파이어는 shape key 만들기 전에 전부 적용.**
- **색 변화 = 뷰어 재질 상태.** Blender 재질을 두 벌 만들지 않는다. 색값은 `stages.json`에 둔다.
- **움직임 = 액션 → NLA push-down → 클립.** 이름 `anim__inject`, `anim__release`.
- 재질은 Principled BSDF만. 텍스처 2K 이하, .blend에 팩.
- 지배 영역(dermatome) 같은 오버레이는 피부 메시의 UV 마스크 텍스처(흑백)로 별도 준비 → `skin__hand:dermatome`.

## 3. 공간·스케일
- 단위: m (실측 스케일, 손목 폭 ≈ 60 mm)
- 원점: 관심 구조 중심 (손목터널: 터널 중심, 유구골 갈고리 레벨)
- 기준 자세: 오른손, 손바닥 위
- export 전 모든 오브젝트 트랜스폼 적용 (Ctrl+A → All Transforms)
- 폴리곤 예산: 총 30만 tri 이하 (태블릿 기준)

## 4. stages.json (Blender 밖, glb 옆에 둔다)
```json
{ "topic": "carpal_tunnel", "attribution": "Z-Anatomy CC BY-SA 4.0",
  "stages": [
    { "id": 1, "name": "외관",     "camera": "cam__1", "variant": "full" },
    { "id": 2, "name": "터널 노출", "camera": "cam__2", "variant": "cut",
      "labels": ["lig__tcl", "nerve__median"] },
    { "id": 3, "name": "병리",     "camera": "cam__3", "variant": "cut",
      "toggle": { "lig__tcl": {"thick": 1}, "nerve__median": {"compressed": 1} },
      "color":  { "nerve__median": "#c0392b" } },
    { "id": 4, "name": "증상",     "camera": "cam__4", "variant": "cut",
      "highlight": ["nerve__median"], "overlay": "skin__hand:dermatome" },
    { "id": 5, "name": "치료",     "camera": "cam__5", "variant": "cut",
      "substeps": [ {"color": {"nerve__median": "#f2d5b8"}},
                    {"play": "anim__inject"},
                    {"swap": {"lig__tcl": "lig__tcl__released_*"},
                     "toggle": {"nerve__median": {"compressed": 0}}} ] }
  ] }
```
필드 의미
- `variant` : 표시할 변형 세트 (`full` = 접미사 없는 노드, `cut` = `__cut` 노드)
- `toggle` : 노드별 morph target 가중치 (0~1, 뷰어가 트윈)
- `color` : 노드별 재질 색 상태
- `labels` / `highlight` / `overlay` / `play` / `swap` : 라벨 표시 / 발광 강조 / UV 마스크 오버레이 / 애니메이션 클립 재생 / 노드 교체
- `substeps` : 한 스테이지 안의 순차 단계 (치료 3단 등)

## 5. 뷰어 UI (외래용)
회전·확대 자유, 이전/다음, 정상/병리 토글, 라벨 on/off. 내레이션·자막 없음(의사가 직접 설명).
모든 페이지에 교육용 고지 + Z-Anatomy 저작자 표시.

## 6. 진행 순서 (주제마다 동일)
1. 스테이지 스크립트 확정 → 2. 에셋 목록·출처 → 3. Blender 씬 구축(이 규칙) → 4. glb + stages.json export → 5. 뷰어에서 검수
