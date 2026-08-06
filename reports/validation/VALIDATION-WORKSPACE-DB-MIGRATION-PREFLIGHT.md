# Workspace DB Migration Preflight 검증 보고서

> 문서 상태: [완료]
> 최종 수정일: 2026-08-06
> 기준 develop: `700dda83b8fd0ce76f460a8f2bc5668a277a7338`
> 관련 기능: 실제 SQLite 사용자 DB 적용 전 안전 Gate
> 실제 사용자 DB 상태: 미접근·미변경
> 관련 문서: [Runbook](../../docs/10-operations/workspace-db-migration-runbook.md), [체크리스트](../../docs/10-operations/workspace-db-preflight-checklist.md), [Backup·Rollback](../../docs/10-operations/workspace-db-backup-rollback-policy.md)

## 1. 검증 범위

- Runtime과 Alembic의 SQLite URL 결정 방식 분석
- read-only Inventory와 schema drift 분류 도구 구현
- 명시적 확인이 필요한 SQLite backup API 경계 구현
- 임시 fixture의 backup·upgrade copy·restore copy rehearsal
- 실제 사용자 DB에 필요한 승인과 중단 Gate 문서화

실제 사용자 DB 파일을 검색하거나 열지 않았고, 실제 경로·크기·row count·checksum을 수집하지 않았습니다.

## 2. DB 위치 결정 분석

| 항목 | 확인 결과 |
|---|---|
| Runtime 설정 | `DATABASE_URL` 환경 변수 우선 |
| Runtime 기본값 | `sqlite:///./backend/storage/doha_music.db` |
| Alembic 기본값 | `backend/alembic.ini`의 같은 상대 URL |
| 상대 경로 기준 | 명령을 실행한 현재 작업 디렉터리 |
| 앱 시작 동작 | lifespan에서 `upgrade_database(database_url)` 실행 |
| 테스트 DB | pytest `tmp_path` 아래 별도 SQLite |
| benchmark DB | 임시 디렉터리 아래 별도 SQLite |
| 실제 경로 출력 | preflight 도구에서 중간 component 마스킹 |

Runtime과 Alembic이 같은 문자열을 기본값으로 갖더라도 실행 작업 디렉터리가 다르면 다른 파일을 가리킬 수 있습니다. 실제 적용 전 하나의 정규화된 파일을 승인해야 합니다.

## 3. 구현한 도구

`backend/db/workspace_preflight.py`는 read-only 검사와 backup 검증을 담당하고, `backend/scripts/workspace_db_preflight.py`는 다음 세 command와 승인 플래그만 제공합니다.

| Command | DB 읽기 | 파일 생성 | Schema·Data 변경 |
|---|---:|---:|---:|
| `plan-backup` | 없음 | 없음 | 없음 |
| `inventory` | 승인 확인 후 read-only | 없음 | 없음 |
| `backup` | 읽기 승인·writer 종료 확인 후 read-only | 명시적 확인 후 새 backup | 원본 변경 없음 |

Alembic upgrade·downgrade, 자동 복구, 파일 삭제 명령은 제공하지 않습니다. 모든 command는 DB 경로를 필수 CLI 인자로 받아 하드코딩된 사용자 경로를 사용하지 않습니다. Inventory는 `--confirm-read-approved`, backup은 여기에 `--confirm-writers-stopped`와 `--confirm-create-backup`까지 요구합니다.

Inventory 항목은 파일 크기·checksum, SQLite version, `application_id`, `user_version`, revision, Table과 row count, integrity·quick·FK 검사, WAL·SHM, journal·FK·synchronous·busy timeout, Runtime schema drift입니다. row 내용은 출력하지 않습니다.

## 4. Fixture 테스트

실제 사용자 DB가 아닌 pytest 임시 디렉터리만 사용했습니다.

1. 기존 migration chain으로 `20260801_0011` fixture를 생성했습니다.
2. Inventory 전후 원본 fixture SHA-256이 동일함을 확인했습니다.
3. Runtime Table 14개, Workspace Table 0개와 무결성을 확인했습니다.
4. 확인 인수 없는 backup 요청이 거부됨을 확인했습니다.
5. SQLite backup API로 timestamp backup을 생성했습니다.
6. backup checksum·integrity·revision·Table 수를 검증했습니다.
7. backup 복사본에만 `20260806_0012`를 적용해 35개 Table을 확인했습니다.
8. 별도 backup 복원본이 `20260801_0011`과 Runtime Table 14개를 유지함을 확인했습니다.

Preflight 전용 테스트는 `3 passed`입니다. 기존 Workspace migration·Entity·Foundation·Voice Enrollment migration 회귀를 함께 실행한 최종 선별 suite는 `14 passed`, 기존 Python 3.12 datetime adapter 경고 6건입니다.

## 5. Schema drift 분류

도구는 Runtime Table 누락, Column nullable, FK와 명시적 Index를 ORM metadata와 비교합니다. 자동 수정은 하지 않습니다.

| 차이 | 분류 | 처리 |
|---|---|---|
| Runtime Table·Column 누락 | BLOCKER | 적용 중단 |
| FK 또는 필수 Index 누락 | BLOCKER | 적용 중단 |
| `pipeline_jobs.input_snapshot` DB nullable·metadata non-nullable | WARNING | 별도 migration에서 정리 |
| 예상 외 Table·Column·Index | WARNING 후 수동 판정 | 원인 확인 전 적용 보류 가능 |
| SQLite 내부 autoindex | 허용 가능한 차이 | 명시적 Index 비교에서 제외 |

Check Constraint와 SQLite DDL의 모든 수동 변경 흔적은 자동 비교만으로 완전하게 판정할 수 없으므로 실제 Inventory에서 `sqlite_master`와 migration history를 추가 검토해야 합니다.

## 6. 실제 적용 BLOCKER

1. 현재 앱은 시작 시 자동으로 `upgrade head`를 실행하므로 preflight 전 앱 실행을 허용할 수 없습니다.
2. Runtime Engine과 Alembic `env.py`가 `PRAGMA foreign_keys=ON`을 명시하지 않습니다.
3. 실제 사용자 DB Inventory·backup·restore rehearsal과 사용자 승인이 아직 없습니다.

이 BLOCKER는 이번 문서·도구 PR에서 Runtime을 변경해 숨기지 않습니다. 별도 수정과 검증 후 실제 적용 승인을 다시 요청해야 합니다.

## 7. WARNING

- Python 3.12 SQLite datetime adapter 폐기 예정
- `pipeline_jobs.input_snapshot` nullable drift
- 순환 FK의 SQLite 외 DB 제품 검증 필요
- 전체 offline chain의 기존 `20260729_0006` live reflection 제한
- `os.access` 기반 쓰기 가능성과 디스크 공간 값은 사전 advisory이며 실제 exclusive writer 확보를 대체하지 않음

## 8. 결론

Preflight 도구와 Runbook은 fixture 기준으로 검증되었습니다. 실제 사용자 DB 적용 판정은 `BLOCKED`입니다. 실제 DB read-only Inventory 승인, FK 연결 정책 수정, 검증된 backup과 최종 적용 승인이 모두 필요합니다.
