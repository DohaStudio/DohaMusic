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
