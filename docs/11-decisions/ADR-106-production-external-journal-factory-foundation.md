# ADR-106: Production External Journal Factory Foundation

> 상태: [제안 — Runtime Factory 구현, journal provisioning/production activation 비활성]
> 작성일: 2026-09-24
> 기준 develop: `cda9fa8bd1974d20d431b5efdc80ec024bfd3a21` (#192 squash merge)
> 관련 결정: [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-100](ADR-100-admission-journal-transaction-owner-foundation.md), [ADR-101](ADR-101-admission-commit-reconciler-foundation.md), [ADR-104](ADR-104-reviewed-production-deployment-configuration-foundation.md), [ADR-105](ADR-105-production-private-authority-source-factory-foundation.md)
> 검증: [Production External Journal Factory 검증](../10-operations/production-external-journal-factory-validation.md)

## 결정

Reviewed production configuration의 digest/schema/version/profile, installation/deployment/journal identity, exact external journal path·filename, journal v1 schema와 event schema/domain을 하나의 immutable descriptor로 결합한다. Runtime Factory는 이 descriptor가 가리키는 **이미 provision된** SQLite journal만 `mode=rw`로 열며 missing file을 생성하지 않는다.

Open은 exact schema object/version, SQLite integrity, journal identity, complete verified event history, GENESIS-shaped revision 1, head/history와 두 번의 동일 snapshot을 요구한다. Wrong identity, empty/missing/unsupported/corrupt/truncated/reset journal은 단일 safe error로 fail closed한다. 기존 v1 schema/repository가 충분하므로 새 schema나 Alembic 변경은 없다.

## Path, lifetime과 handoff

ADR-104 canonical path parser를 재사용하고 모든 directory component와 journal leaf를 `OPEN_EXISTING`/`OPEN_REPARSE_POINT` native handle로 고정한다. Exact final path, no reparse, leaf hardlink count 1과 volume/file identity를 runtime lifetime 동안 재검증한다. 하나의 pinned SQLite connection은 일반 rename/delete replacement를 막고 Transaction Owner와 Reconciler가 동일 opened file을 사용하게 한다. Identity/path drift나 cleanup failure는 ready로 변환하지 않고 runtime을 거부한다.

Factory는 동시에 하나의 thread-bound root Session capability만 발급한다. Capability는 exact runtime/transaction에 결합되고 orderly close 뒤 재사용할 수 없다. 기존 Transaction Owner만 commit/rollback을 소유하고 Reconciler는 동일 Engine의 독립 read snapshot만 사용한다. Factory, Fresh Observation과 Reconciler에는 DML·commit authority가 없다.

## Provisioning과 authority 경계

Runtime open은 provisioning이 아니다. Factory는 DB/schema/journal identity/GENESIS를 생성하거나 migration, repair, history rewrite, app DB·memory·test fallback을 수행하지 않는다. Installation/deployment 값은 reviewed routing binding이며 journal 자체에서 새로운 installation authority를 발명하지 않는다.

Factory 성공은 journal provisioning, custody, authentication, admission 또는 activation 성공이 아니다. 실제 production journal 생성·초기 ACL/custody·identity/GENESIS 확립은 별도 Provisioning Contract/Foundation 책임이다. Production Authentication Wiring과 final Activation Gate도 후속 dependency이며 기본 production composition은 계속 unavailable이다.
