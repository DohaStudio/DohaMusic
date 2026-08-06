# Frontend dependency 기준선 검증

> 문서 상태: [완료]
> 검증일: 2026-08-06
> 기준 브랜치: `develop`
> 기준 commit: `e0131d39c9ed0ab0053a5e18e3ad50867470d56b`
> 작업 브랜치: `fix/frontend-dependency-baseline`
> 관련 문서: [코드 기준선 안정화 검토](VALIDATION-WORKSPACE-CODE-BASELINE.md), [변경 이력](../../CHANGELOG.md)

## 1. 결론

Frontend dependency 기준선의 BLOCKER를 해소했다.

- `npm ci`: PASS
- `npm ls`: PASS, `problems`와 `ELSPROBLEMS` 0건
- `npm audit`: 전체 취약점 0건
- lint·typecheck·production build·Vitest: PASS
- Frontend dependency 관점의 `main` 승격 BLOCKER: 0건
- PR #55: 미변경·미포함

이번 판정은 Frontend dependency 범위에 한정한다. 작업 브랜치를 `develop`에 병합한 뒤 최신 `develop`에서 전체 코드 기준선 Gate를 다시 확인해야 한다.

## 2. 실행 환경

| 항목 | 값 |
|---|---|
| 운영체제 | Windows |
| Node.js | `v24.15.0` |
| npm | `11.12.1` |
| lockfileVersion | `3` |
| Next.js | `16.2.12` |
| React·React DOM | `19.2.8` |
| TypeScript | `5.9.3` |
| Vitest | `4.1.10` |

현재 GitHub Actions에는 Frontend 설치·검증 Workflow와 고정된 Node.js 버전이 없다. 로컬 검증은 Next.js가 요구하는 Node.js `>=20.9.0` 범위에서 수행했지만, 재현 가능한 CI Node.js 버전 고정은 후속 WARNING으로 남긴다.

## 3. 수정 전 상태

이전 코드 기준선 보고서는 audit 결과를 high 2건·moderate 2건으로 기록했다. 이번 작업에서 같은 기준 commit을 2026-08-06의 npm Registry·Advisory 기준으로 다시 설치하자 15 high·2 moderate 경로가 보고됐다. audit 결과는 Advisory 갱신에 따라 달라질 수 있으므로 이번 보고서는 실제 재검증 값을 기준으로 한다.

### npm ls

- 기존 `sharp 0.35.0` 전역 override가 설치한 `@img/sharp-wasm32 0.35.0`과 `@emnapi/runtime 1.11.3`이 `extraneous`로 표시됐다.
- npm 11.12.1의 일반 출력과 JSON에 두 `problems`가 재현됐다.
- 기존 기준선에서 기록한 override·lockfile `ELSPROBLEMS`를 해소하려면 설치 결과와 manifest의 관계를 일치시켜야 했다.

### npm audit

| 근본 패키지 | 심각도 | 경로 | 관계 | 안전 버전 | Breaking change | Frontend 영향 |
|---|---|---|---|---|---|---|
| `brace-expansion 5.0.8` | high | ESLint 계열 → `minimatch` → `brace-expansion` | 전이·개발 | `>=5.0.9` | 없음, 5.0.x 패치 | 악의적 glob 처리 시 자원 고갈 가능성이 있으나 production bundle에는 노출되지 않음 |
| `postcss 8.5.18` | moderate | `next` → `postcss` | 전이·production build | `>=8.5.23` | 없음, 8.5.x 패치 | 신뢰하지 않은 source map 입력을 처리할 때 파일 노출 가능성 |
| `sharp <0.35.0` | high | `next` → optional `sharp` | 전이·production | `>=0.35.0` | 0.34.x 대비 major 경계 | 이미지 처리 시 libvips 취약점 영향 가능 |

`next`, `eslint`, `eslint-config-next`, `typescript-eslint` 등 17개 audit 항목 대부분은 위 근본 패키지에서 파생된 영향 경로다. Next.js를 `16.3.0`으로 올리거나 `eslint-config-next`를 15.x로 내리는 audit 자동 제안은 프레임워크 범위를 넓히므로 적용하지 않았다.

## 4. 변경 내용

| 항목 | 수정 전 | 수정 후 | 적용 이유 |
|---|---|---|---|
| `brace-expansion` override | `5.0.8` | `5.0.9` | high Advisory의 최소 안전 패치 적용 |
| `minimatch` override | `10.2.3` | `10.2.6` | 기존 10.x 정책을 유지하며 안전한 패치와 중복 node 정리 |
| `postcss` override | `8.5.18` | `8.5.25` | 8.5.x 범위에서 moderate Advisory 수정 버전 적용 |
| `sharp` dependency | 없음 | `0.35.0` | 기존 override로 이미 사용·검증한 안전 버전을 production 직접 의존성으로 명시 |
| `sharp` override | `0.35.0` | `0.35.0` | Next.js의 취약한 optional `sharp ^0.34.5`를 계속 대체 |
| `@img/sharp-wasm32` | lockfile orphan | optional `0.35.0` | npm 11이 설치하는 공식 sharp WASM 패키지를 manifest에 연결해 `extraneous` 제거 |

`sharp 0.35.0`은 이번 작업에서 새로 자동 major 업그레이드한 버전이 아니다. 기존 `develop`의 override와 이전 production build가 이미 같은 버전을 사용했으며, 이번 변경은 해당 선택을 직접 dependency로 명시해 lockfile과 설치 트리를 일치시킨 것이다.

lockfile은 기존 graph를 기준으로 npm이 다시 계산했다. 의도한 버전 변경은 `brace-expansion`, `minimatch`, `postcss` 세 패키지이며, override로 중복되던 nested `minimatch`와 `postcss` node가 제거됐다. 무관한 범위 dependency의 최신화는 포함하지 않았다.

## 5. 수정 후 검증

| 검증 | 결과 | 세부 결과 |
|---|---|---|
| `npm ci` | PASS | 459개 package 설치, 460개 audit, 취약점 0건 |
| `npm ls --all --json` | PASS | 전체 전이 tree 종료코드 0, `problems` 없음, invalid·extraneous·peer 오류 0건 |
| `npm audit --json` | PASS | critical 0, high 0, moderate 0, low 0 |
| `npm run lint` | PASS | ESLint 오류 없음 |
| `npm run typecheck` | PASS | `tsc --noEmit` 오류 없음 |
| `npm run test` | PASS | 20개 Test File, 97개 Test 통과 |
| `npm run build` | PASS | Next.js 16.2.12, 12개 Route production build 성공 |

production build는 Google Fonts 접근이 가능한 네트워크 환경에서 수행했다. Google Fonts 네트워크 의존은 dependency BLOCKER와 별개의 기존 WARNING이다.

## 6. 범위와 격리

- Frontend 기능·UI·소스 코드는 변경하지 않았다.
- Next.js·React·TypeScript 직접 버전은 유지했다.
- Backend·SQLAlchemy Entity·Alembic·Runtime·Provider는 변경하지 않았다.
- `node_modules`, `.next`, Dataset·모델·Checkpoint·미디어 파일은 Git에 포함하지 않는다.
- 원본 작업 트리의 `frontend/next-env.d.ts` 사용자 변경은 격리 clone과 PR diff에 포함하지 않는다.
- PR #55 commit `17eaf2cdf38ab79ddaa97885a66e2898cbec8e47`과 `backend/models/workspace/*`는 포함하지 않는다.

## 7. 판정

| 등급 | 결과 | 설명 |
|---|---|---|
| PASS | Frontend dependency Gate | 깨끗한 설치·tree·audit·lint·typecheck·test·build 통과 |
| WARNING | Frontend CI Node.js 미고정 | 저장소 Workflow에 Frontend Node.js 버전과 dependency Gate가 아직 없음 |
| WARNING | Google Fonts 네트워크 의존 | 네트워크가 차단된 build 환경에서는 별도 실패 가능 |
| BLOCKER | 0건 | high 취약점·tree 오류·회귀 검증 실패 없음 |

Frontend dependency 관점에서는 `main` 승격이 가능하다. 다만 이 PR을 `develop`에 병합하고 최신 `develop` 전체에서 기존 WARNING과 코드 기준선 조건을 다시 확인한 뒤에만 `develop → main` Draft PR을 생성한다.
