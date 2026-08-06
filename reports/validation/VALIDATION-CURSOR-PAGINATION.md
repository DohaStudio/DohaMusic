# HMAC Cursor Pagination 기반 검증 보고서

> 문서 상태: [완료]
> 검증일: 2026-08-06
> 기준 브랜치: `feature/cursor-pagination`
> 기준 develop: `e5681db0443feb47a44da639f0ac31abb69a6bc3`
> 관련 문서: [Cursor Pagination 설계](../../docs/06-api/cursor-pagination.md), [Workspace REST API 계약](../../docs/06-api/workspace-rest-api-contract.md)

DohaStudio Common Specification `0.1.0` / `draft-baseline`의 `main` 기준선을 확인했으며, 이번 변경은 공통 Asset·Job·Artifact 계약이나 명세 버전을 변경하지 않습니다.

## 1. 검증 범위

- HMAC-SHA256 Cursor encode·decode와 canonical token
- 전용 `SecretStr` 환경 설정과 32바이트 최소 길이
- version·Resource·정렬·filter·limit·datetime·UUID 검증
- `v`·`limit`의 Boolean·실수·문자열 거부와 Service 정수 경계 검증
- 2 KiB Cursor 최대 길이와 공개 placeholder key 차단
- Workspace·Project `(created_at DESC, UUID DESC)` keyset 조회
- `limit + 1`, `has_more`, `next_cursor` 불변 조건
- 같은 생성 시각의 복수 row와 여러 page 중복·누락
- Soft Delete 제외와 Workspace·owner filter 고정
- 서로 다른 생성 시각의 정렬과 page 사이 insert·Soft Delete 후 forward-only 동작
- 기존 API Router·OpenAPI·metadata·Alembic 불변성

실제 사용자 DB, 실제 secret, Bootstrap, Resource Endpoint, Frontend와 Provider는 사용하지 않았습니다. DB 검증은 pytest가 생성한 temporary SQLite만 사용했습니다.

## 2. 보안 계약

Cursor payload에는 version, Resource, 방향, 정렬, 마지막 생성 시각·UUID, filter hash와 limit만 존재합니다. owner ID와 Workspace ID를 포함한 filter 원문, 이름·제목, DB 경로, SQL, Table명과 credential은 포함하지 않습니다.

서명은 canonical JSON bytes에 HMAC-SHA256을 적용하고 `compare_digest`로 검증합니다. 형식·서명·payload 검증 실패는 모두 외부 `INVALID_CURSOR`로 통합되며 내부 reason, 서명값과 payload 원문은 응답 메시지에 노출하지 않습니다. 설정의 실제 비밀값은 `SecretStr` repr에서 숨겨집니다.

## 3. 자동 검증 결과

| 검증 | 결과 |
|---|---|
| Cursor·keyset 전용 테스트 | PASS — 27 passed |
| API 기반·Bootstrap·Service·Repository·Entity·Migration 선별 회귀 | PASS — 78 passed |
| 전체 Backend suite 최종 재실행 | PASS — 339 passed, 7 skipped |
| Python compile | PASS |
| Ruff lint | PASS |
| Ruff format check | PASS |
| Alembic head | PASS — `20260806_0012` |
| Alembic revision 변경 | PASS — 0개 |
| Route·OpenAPI | PASS — Route 45, APIRoute 41, path 34, operation 43, v1 Resource path 0 |
| SQLAlchemy metadata | PASS — 35개 Table |

기반 구현의 전체 Backend suite 최초 실행은 `329 passed, 7 skipped, 1 failed`였습니다. 실패 1건은 `test_pipeline_file_access_api.py`가 Windows에서 사용 중인 `final.wav`를 삭제할 때 발생한 파일 잠금 오류이며 Cursor 코드와 관련된 assertion 실패가 아닙니다. 당시 단독 재실행과 전체 suite 재실행에서 정상 통과했고, 이번 경계 보완 후 전체 suite는 `339 passed, 7 skipped`로 통과했습니다.

기존 Pipeline file Route의 OpenAPI operation ID 중복 2건과 Python 3.12 SQLite datetime adapter 폐기 예정 경고는 이번 범위 밖 WARNING으로 유지합니다.

## 4. Page 불변 조건

- 0개와 마지막 page: `has_more=false`, `next_cursor=null`
- `limit`를 정확히 채우고 다음 row가 없음: `has_more=false`
- 다음 row 존재: `has_more=true`, 서명된 `next_cursor` 필수
- 다음 page는 직전 page 마지막 `(created_at, UUID)`보다 작은 keyset만 조회
- 같은 `created_at` row는 UUID DESC로 결정적 정렬
- 다른 Resource·Workspace·owner filter와 다른 limit에는 cursor 재사용 불가
- 외부 offset 노출과 Repository offset 사용 없음
- page 사이 insert·delete가 발생해도 이미 반환한 row를 재반환하거나 무한 반복하지 않음

Cursor는 여러 요청에 걸친 전체 목록의 snapshot isolation을 보장하지 않습니다. page 이후 생성된 상위 row는 이전 cursor가 다시 탐색하지 않으며 후속 row가 삭제되면 결과에서 제외됩니다.

## 5. 판정

Cursor Pagination 기반 자체의 BLOCKER는 없습니다. Workspace·Project Resource Endpoint는 아직 없으며 후속 PR에서 app composition, `limit`·`cursor` Query와 Collection Envelope를 연결해야 합니다.

서명 키 교체와 cursor 만료는 운영 전 확정할 WARNING입니다. 이번 구현은 서명 키가 바뀌면 기존 cursor가 안전하게 `INVALID_CURSOR`가 되는 방식이며 별도 grace key는 제공하지 않습니다. 현재 Workspace·Project keyset 정렬용 복합 Index도 Resource Endpoint 운영 연결 전 별도 Migration에서 실제 Query Plan을 기준으로 추가해야 합니다.
