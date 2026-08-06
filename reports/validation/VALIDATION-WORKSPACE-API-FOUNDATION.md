# Workspace API 기반·Bootstrap 검증 보고서

> 문서 상태: [완료]
> 검증일: 2026-08-06
> 대상 브랜치: `feature/workspace-api-foundation`
> 기준 develop: `fceeb07ae9d3c421b11255a6395e6271a59dcc48`
> 실제 사용자 DB 접근: 없음

## 1. 검증 범위

- `/api/v1` 빈 Router와 기존 `/api` Route 호환성
- 공통 성공·Collection·오류 Schema
- request ID 생성·검증·payload·Header 전달
- v1 Application·validation·내부 오류 분기
- 명시적 Workspace Bootstrap dry-run·apply·멱등·rollback
- Workspace Service·Repository·Entity·Migration과 Runtime 회귀

## 2. 테스트 결과

| 범위 | 결과 |
|---|---:|
| Workspace API 공통 기반 | 11 passed |
| Workspace Bootstrap | 11 passed |
| Workspace Service | 13 passed |
| Workspace Repository·Entity·Migration 안전 | 26 passed |
| 기존 Runtime 선별 회귀 | 12 passed |
| **합계** | **73 passed** |

검증 시나리오는 request ID, v1 미등록 경로 404, 기존 Runtime application·validation·기본 404 payload, 내부 경로 비노출, Route 수, 기존 operation ID 경고, DB 미생성 dry-run, URL·이름 입력 차단, revision·Table gate, 최초 생성·재실행, owner 불일치·다중 Workspace 중단, Soft Delete 미복구와 rollback을 포함합니다.

초기 신규 테스트에서 OpenAPI 중복을 route `unique_id`와 고정 GET·HEAD suffix로 판단한 테스트 오류 1건씩을 발견했습니다. FastAPI가 set 기반 Method에서 suffix를 비결정적으로 선택하는 기존 동작을 확인한 뒤, 생성된 OpenAPI에서 중복 2개의 안정적인 경로 base만 검사하도록 고쳤습니다. 제품 코드 실패는 아니며 최종 11개 API 기반 테스트가 통과했습니다.

## 3. 정적·구조 검증

### GitHub Actions Route 회귀 수정

- 최초 PR head `464e4f138127e49ecded7ca091d20e5348fb5313`의 `backend-ubuntu`에서는 FastAPI `0.141.1`·Starlette `1.4.1`이 설치됐고, 중첩 Router를 최상위 `app.routes`에 펼치지 않는 내부 표현 때문에 Route 계약 테스트 1건이 실패했다.
- Runtime Endpoint와 OpenAPI 계약은 정상이며 전역 Router 상태 누수나 test-order 의존성은 재현되지 않았다. 같은 의존성 조합에서는 해당 테스트를 단독 실행해도 동일하게 실패했다.
- 테스트가 FastAPI 내부 저장 형태 대신 등록 Route를 재귀적으로 정규화해 전체 45개와 `APIRoute` 41개를 확인하고, OpenAPI 34개 경로·43개 operation·기존 `/api` 경로 33개·`/api/v1` Resource 경로 0개를 별도로 확인하도록 수정했다.
- CI 의존성 격리 환경의 전체 Suite는 `312 passed, 7 skipped`, 기존 73개 선별 케이스는 `72 passed, 1 skipped`로 통과했다. 선별 검증의 1개 skip은 Windows symlink 권한에 따른 기존 동작이며 Linux Actions에서는 실행 대상이다.
- 저장소 검증 기준 Ruff `0.15.22`의 `ruff check backend`와 CI Ruff `0.16.1`의 변경 범위 검사는 통과했다. Ruff `0.16.1`로 전체 Backend를 검사하면 이 PR 이전 파일에서 새 규칙 위반 38건을 추가로 보고하므로 별도 기준선 정리 WARNING으로 남긴다.

- Python compile: PASS
- Ruff lint: PASS
- Ruff format: PASS, Backend 250개 파일
- `git diff --check`: PASS
- Markdown 상대 링크·fence: PASS
- FastAPI Route: 45개
- v1 Resource Route: 0개
- SQLAlchemy metadata: 35개 Table
- Alembic head: `20260806_0012`
- 신규 Alembic revision: 0개
- 비밀정보·Dataset·모델·Checkpoint·미디어: 없음

## 4. 안전 경계

- 테스트는 명시적 임시 SQLite만 사용합니다.
- 실제 `DATABASE_URL`, 실제 DB 파일과 사용자 Workspace row에 접근하지 않습니다.
- CLI dry-run은 DB를 열지 않습니다.
- `--apply` 테스트도 fixture DB에서만 실행합니다.
- Alembic revision, Runtime Table schema와 row를 변경하지 않습니다.

## 5. 미구현·WARNING

- 64개 Resource Endpoint
- 일반 Workspace Idempotency-Key 저장·재생
- HMAC cursor codec과 keyset pagination
- Artifact Resolver·content·download
- Job dispatch·Provider 연결
- 실제 기본 Workspace Bootstrap
- 기존 Pipeline file Route의 OpenAPI operation ID 중복 2건
- owner 단위 DB Unique Constraint가 없어 동시 Bootstrap 최종 방어는 후속 검토 필요
