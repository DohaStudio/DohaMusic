# Artifact Storage Resolver 검증

> 문서 상태: [완료]
> 검증일: 2026-08-10
> 기준 브랜치: `feature/artifact-storage-resolver`
> 기준 develop: `35b92fc9d6a7b430cc11675e79ac48990cf1fbc5`
> 관련 문서: [Artifact Storage 계약](../../docs/03-architecture/artifact-storage-contract.md), [ADR-032](../../docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md)

## 1. 검증 범위

이번 검증은 `ArtifactStorageLocation` 조회와 `local` Payload의 안전한 read-only 해석만 대상으로 했다. 모든 파일 검증은 테스트 전용 임시 directory와 mocked Catalog 또는 임시 SQLite에서 수행했다. 실제 사용자 DB, 실제 `DohaArtifacts`, Catalog 운영 row와 사용자 Payload에는 접근하지 않았다.

Alembic revision, Entity, Artifact API, Frontend, Runtime, trusted ingestion, 파일 publish·copy·move·delete, checksum DB 등록과 backfill·dual write는 변경하지 않았다.

## 2. 구현 경계

| 구성 요소 | 구현 결과 |
|---|---|
| Catalog 조회 | `ArtifactStorageRepository.get_storage_location()` read-only 조회, transaction·filesystem 책임 없음 |
| 설정 | 선택적 `DOHA_ARTIFACT_ROOT`; 기본 미설정, 네 domain directory가 안전하지 않으면 fail-closed |
| backend | `local`과 locator version `1`만 허용, 자동 fallback 없음 |
| domain | `lm`, `audio`, `vocal`, `music`만 허용 |
| key | canonical POSIX 상대 key, 빈 segment·dot segment·역슬래시·절대/drive/UNC/URI·percent·control·Windows 예약 이름 거부 |
| `music` namespace | `mixes`, `exports`, `previews`, `snapshots`, `runs`만 허용 |
| containment | `Path.relative_to()` 기반 root ancestry 확인, 문자열 prefix 비교 없음 |
| link 방어 | component별 symlink·junction·reparse point 거부 |
| 파일 종류 | 존재하는 regular file만 허용, 누락·directory·device 계열 거부 |
| TOCTOU 최소 방어 | `os.open()` descriptor와 path의 identity를 비교하고 size·mtime·identity가 같은 handle인지 재검증 |
| 내부 결과 | Pydantic 공개 DTO가 아닌 frozen `ResolvedArtifactPayload` dataclass |
| 오류 | 안전한 내부 코드와 일반 메시지만 반환하며 실제 path·storage key를 포함하지 않음 |

Owner scope와 `retention_status`는 Resolver에 넣지 않았다. 향후 Artifact Application Service가 `Artifact → AssetVersion → Asset` 권한과 lifecycle을 확인한 뒤 Resolver를 호출해야 하며 Router의 직접 호출은 금지한다. Resolver는 전체 SHA-256·MIME 검증을 수행하지 않으므로 Artifact integrity 완료로 판정하지 않는다.

## 3. 신규 보안 테스트

`backend/tests/test_artifact_storage_resolver.py` 결과는 `39 passed, 2 skipped`다.

- 정상 local/music·nested key·네 domain 분리·Catalog lookup·regular file과 같은 descriptor open을 확인했다.
- missing Catalog, unsupported backend·locator version, invalid domain을 거부했다.
- 빈 key, `.`, `..`, traversal, POSIX absolute, Windows drive·UNC, URI, 역슬래시, NUL/control, percent encoding, malformed segment와 승인되지 않은 music namespace를 거부했다.
- missing file과 directory target을 `ARTIFACT_CONTENT_UNAVAILABLE`로 거부했다.
- 파일 교체 뒤 identity·size·mtime 불일치를 거부했다.
- Windows 권한 제약으로 실제 symlink 생성 2건은 조건부 skip했다. 별도 reparse component 감지 시뮬레이션은 통과해 fail-closed 분기를 검증했다.

## 4. 회귀 검증

| 범위 | 결과 |
|---|---:|
| Artifact Storage Resolver | 39 passed, 2 skipped |
| Artifact Storage Catalog·0016 | 10 passed |
| Workspace Entity | 6 passed |
| Workspace Repository | 8 passed |
| Workspace Service | 13 passed |
| Asset·AssetVersion API | 18 passed |
| API Foundation·Route/OpenAPI | 11 passed |
| Workspace·Project·ProjectAsset Router | 28 passed |
| Workspace additive Migration | 2 passed |
| 합계 | 135 passed, 2 skipped |

큰 묶음으로 실행한 두 회귀 명령은 각각 120초와 240초 제한에서 중단되어 통과로 계산하지 않았다. 같은 필수 파일을 작은 묶음으로 다시 실행해 위 결과를 회수했다. GPU·외부 Provider·Dataset·실제 DB 테스트와 전체 Backend suite는 이번 범위에서 실행하지 않았다.

## 5. 불변 기준

- Python 3.12.5 `compileall`: PASS
- Ruff 전체 Backend lint·format check: PASS
- `git diff --check`: PASS
- 변경 Markdown 19개 UTF-8·fence·상대 링크: PASS
- SQLAlchemy metadata: 36개 Application Table 유지
- Alembic 단일 head: `20260809_0016` 유지
- FastAPI: Route 64개, APIRoute 60개 유지
- OpenAPI: Path 44개, Operation 62개 유지
- Resource API: 19/64 유지
- Artifact API: 0/3 유지
- 실제 사용자 DB: 문서 기준 `20260809_0016`, 미접근
- Runtime Table 14개: source of truth 유지

## 6. 판정

BLOCKER는 0건이다. Resolver read-only 기반은 구현·격리 검증됐지만 다음 항목은 의도적으로 남은 WARNING 또는 후속 Gate다.

- Windows 권한이 있는 CI·운영과 동등한 파일 시스템에서 실제 symlink·junction·reparse escape 재검증 필요
- Artifact root의 write 권한을 trusted ingestion으로 제한하는 운영 ACL 검증 필요
- trusted ingestion, authoritative SHA-256·size·MIME 검증과 orphan reconciliation 미구현
- owner·retention Application Service와 Router 연결 미구현
- Range·content·download를 포함한 Artifact API 3개 미구현
- 기존 OpenAPI Pipeline operation ID 중복 경고와 TestClient 의존성 폐기 예정 경고 유지

최종 판정은 **PASS — Resolver 구현 완료, Artifact integrity·delivery는 미완료**다.
