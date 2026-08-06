# SQLite Migration 안전 제어 검증

> 문서 상태: [완료]
> 최종 수정일: 2026-08-06
> 검증 범위: startup 자동 Migration 통제와 Runtime·Alembic SQLite FK 활성화
> 제외 범위: 실제 사용자 DB Inventory·backup·upgrade·downgrade·restore
> 관련 문서: [Migration Runbook](../../docs/10-operations/workspace-db-migration-runbook.md), [Preflight 체크리스트](../../docs/10-operations/workspace-db-preflight-checklist.md)

## 1. 변경 전 위험

`backend/app/factory.py`의 lifespan은 storage 초기화 직후 조건 없이 `upgrade_database(database_url)`을 호출했습니다. 이 helper는 Runtime `DATABASE_URL`을 Alembic 설정에 전달해 `command.upgrade(config, "head")`를 실행했고, 실패 예외는 startup 밖으로 전파되어 앱 시작을 중단했습니다. 일반 pytest fixture와 임시 benchmark도 이 암묵 동작에 의존했습니다. `backend/db/session.py`와 `backend/alembic/env.py`는 SQLite 연결마다 `PRAGMA foreign_keys=ON`을 설정하지 않았습니다. 따라서 사용자 DB를 가리킨 앱 실행만으로 최신 revision이 적용될 수 있고, 연결별 FK 검증이 비활성화될 수 있었습니다.

## 2. startup 정책

- `Settings.auto_migrate`와 `DOHAMUSIC_AUTO_MIGRATE`의 기본값은 `false`입니다.
- 기본 startup은 `upgrade_database()`를 호출하지 않고 자동 변경이 없다는 경고와 수동 preflight 필요성을 기록합니다.
- 앱 startup은 기본 상태에서 DB revision을 조회하지 않습니다. 실제 DB를 임의로 열지 않기 위해 현재·기대 revision 비교는 명시적 읽기 승인이 필요한 `workspace_db_preflight inventory`로 분리합니다.
- `true`를 명시한 경우에만 기존 `upgrade_database()`를 호출합니다. 저장소의 일반 테스트 fixture와 임시 benchmark DB만 이 opt-in을 사용합니다.
- 로그에는 DB URL, credential 또는 절대 경로를 넣지 않습니다.

## 3. SQLite FK 정책

`backend/db/sqlite.py`의 공통 helper가 SQLite Engine의 `connect` event에 PRAGMA 설정을 등록합니다. Runtime session engine과 Alembic online engine이 같은 helper를 사용하며, non-SQLite dialect에는 event를 등록하지 않습니다. Alembic은 migration transaction을 시작하기 전에 raw DBAPI read로 활성 값이 `1`인지 확인하므로 revision 기록 transaction을 방해하지 않습니다. offline SQL 모드는 실제 연결이 없어 이 절차를 실행하지 않습니다.

기존 `0010` batch migration은 이미 참조되는 `voice_profiles` Table을 교체하므로 FK가 켜진 SQLite에서 실행할 수 없습니다. 해당 과거 revision의 데이터 backfill 회귀 테스트만 Alembic `Config.attributes`의 명시적 내부 호환 플래그로 FK를 잠시 끄고, 완료 직후 다시 켠 다음 `foreign_key_check`를 강제합니다. 기본 CLI·Runtime과 실제 목표 경로 `0011 → 0012`에서는 이 플래그를 설정하지 않으므로 FK는 계속 활성화됩니다. 기존 revision 파일은 수정하지 않았습니다.

## 4. 검증 항목

- file·in-memory Runtime SQLite 연결의 `foreign_keys=1`
- FK 위반 insert의 `IntegrityError`
- non-SQLite dialect의 PRAGMA event 미등록
- 설정 누락과 명시적 `false`에서 Migration helper 호출 0회
- 실제 FastAPI lifespan 기본 startup에서 Migration helper 호출 0회
- 명시적 `true`에서 Migration helper 호출 1회
- Alembic 임시 DB upgrade·downgrade와 online FK Gate
- Alembic head `20260806_0012` 유지와 revision 파일 무변경
- 기존 Migration·Preflight와 Backend 선별 회귀
- Python compile, Ruff lint·format, `git diff --check`

검증 결과는 다음과 같습니다.

- Backend 핵심 단위: `120 passed`
- Migration 안전·Workspace round-trip·Preflight·기존 backfill: `17 passed`, Python 3.12 datetime adapter 경고 6건
- Pipeline·Generation·Voice Enrollment 대표 API smoke: `4 passed`
- FK 활성화로 드러난 maintenance orphan fixture 회귀: 수정 후 `1 passed`
- 합계: 중복 없는 선별 테스트 `142 passed`
- Python compile, Ruff lint·format, Alembic 단일 head와 `git diff --check`: 통과

전체 비통합 suite 단일 실행은 5분, 병렬 분할 실행은 10분 제한을 넘겨 완료 결과를 회수하지 못했습니다. 이를 통과로 기록하지 않으며 외부 API·GPU·실제 모델 테스트도 실행하지 않았습니다. 모든 DB 검증은 pytest가 생성한 임시 SQLite DB만 사용했습니다. 실제 사용자 DB를 검색하거나 읽거나 복사하거나 변경하지 않았습니다.

## 5. BLOCKER 상태

해소:

- 앱 startup 자동 `upgrade head` 기본 실행
- Runtime SQLite 연결의 FK 미활성화
- Alembic online SQLite 연결의 FK 미활성화

남음:

- 실제 사용자 DB read-only Inventory 미수행
- 검증된 실제 backup 미생성
- 최종 Migration 적용 승인 없음

## 6. WARNING

- Python 3.12 SQLite datetime adapter 폐기 예정
- `pipeline_jobs.input_snapshot` nullable drift
- 순환 FK의 다른 DB 제품 호환성 재검토 필요
- 기존 `20260729_0006` reflection 제약으로 전체 offline chain 생성 불가
- opt-in 자동 Migration은 임시·테스트 DB 외 사용 전에 별도 승인과 Runbook Gate가 필요
- `0009 → 0010` 데이터 backfill은 SQLite batch 교체 때문에 테스트 전용 명시적 FK 호환 창을 사용함
