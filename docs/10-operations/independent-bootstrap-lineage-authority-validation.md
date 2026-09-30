# Independent Bootstrap Lineage Authority Decision 검증

> 문서 상태: [Decision 검토 — docs-only, 운영 비활성]
> 최종 수정일: 2026-09-30
> 기준 develop: 83d63f8908a4efb35a62aba95824fca87879f860
> 관련 문서: [ADR-107](../11-decisions/ADR-107-independent-bootstrap-lineage-authority.md), [Phase 9 DoD](../DoD/Phase-09.md)

## 범위와 기준선

사용자가 제공한 이전 develop 6717bcd에서 원격을 다시 확인했고 PR #194 merged의 83d63f8을 작업 기준으로 사용했다. main은 63633d462043ad3ba78fee92473d19e90c361431이다. 별도 clean worktree와 docs/independent-bootstrap-lineage-authority 브랜치를 사용하고 원래 workspace의 사용자 변경을 보존했다.

이전 감사의 approval 확장·ADR-093/094 scope 확대 기각을 유지한다. 이번 요청이 새로 허용한 durable authority domain의 소유자/commissioning/등록/소비/보존을 ADR-107에서 결정했다. 실제 지정 human·외부 registry·독립 checkpoint가 존재한다고 주장하지 않는다. 설계 DECIDED, Draft 검토/병합 전이며 구현과 운영은 BLOCKED다.

## 설계 검토 evidence

| 검토 대상 | 확인한 경계 |
|---|---|
| ADR-076 §2/5/6/8/9 | 외부 human assertion·initializer 독립 대조, 별도 lifecycle, privileged full rollback 한계, irreversible seal, Recovery/Transfer 제외 |
| ADR-078 §2/5/6 | no-prior evidence 필요, target journal self-authorization 금지, 분산 atomicity 미가정 |
| ADR-084 | 서면 designation과 authentic source 대조. unsigned designation을 mandatory signed designation으로 바꾸지 않음 |
| ADR-042 | runtime human WebAuthn proof와 외부 provisioning ceremony 구분. runtime 인증 우회 없음 |
| ADR-093/094 | INSTALLATION_POLICY_PROVISIONING_ONLY 보존; scope promotion 없음 |
| ADR-099 및 admission_attempt.py | GENESIS는 existing admission 경로에서 명시 deny |
| currentness_ports.py | unavailable production port 그대로 |
| ADR-104/105/106 | configuration/descriptor는 authority 아님, Factory existing-only 유지 |

ADR-107 §3은 storage 후보 3개를 요청된 16개 기준으로 비교한다. §6은 reservation/commit-after/consume-first/prepare-finalize의 crash window를 비교하고 consume-first + 감사 finalize를 선택한다. consumption commit 후 journal 실패는 권한을 잃는 fail-closed 결과이며 자동 retry하지 않는다.

Circularity 검토 결과: 설계 dependency에 target journal → initial registry authentication 또는 새 record → 자기 최초 승인 edge를 두지 않았다. 최초 신뢰는 기존 ADR-076의 외부 governance assertion에서 끝나며 positive origin·complete coverage의 human 확인을 명시 trust assumption으로 둔다. row 없음·signature만·config·UUID·app DB를 그 근거로 삼지 않는다. 이는 문서상의 순환 의존 제거이며 실제 인증/내구성 구현 검증 결과가 아니다.

## 정적 검증과 한계

- git diff --check: 변경 문서의 trailing whitespace를 정리한 뒤 통과.
- 변경 Markdown 13개·상대 파일 링크 546개: strict UTF-8 decoding, replacement character 없음, fenced block 균형, 상대 파일 링크 대상 존재 검증. 외부 HTTP URL과 GitHub 자동 heading anchor의 전수 네트워크 검증은 하지 않음.
- ADR index: ADR-107 번호 충돌 없음, 단일 파일과 단일 table entry 연결. 기존 ADR-106의 index Draft 표기는 #193 merged로 정합화했고 역사 ADR 본문은 보존.
- Contradiction scan: README/ROADMAP/Master 및 docs/·planning/의 모든 Markdown을 검색했다. 새 보고서 포함 332개 파일에서 31개 후보 문장을 검토했다(역사 문구 8, 현재/새 Decision 23). current architecture의 즉시 Provisioning NEXT 표현을 IBLA source/persistence/checkpoint 선행 계약으로 변경. historical ADR·이전 validation의 당시 NEXT 문구는 보존했다. 현재 root semantics·policy-purpose·GENESIS deny·Factory existing-only·production unavailable와 새 Decision의 충돌을 검토했다.
- application Alembic heads 실제 실행: 20260918_0037 (head), single head. schema·migration 변경 0. actual user DB/production journal/key/credential/WebAuthn/production filesystem 접근 0.
- Full Backend/Frontend/AI 실험: 코드·설정 변경이 없으므로 실행하지 않음. 이전 PR 테스트 수치를 이번 변경 검증으로 재사용하지 않음.

## 문서 영향과 잔여 Gate

README, ROADMAP, MASTER_ROADMAP, bootstrap/lifecycle/issuance architecture, journal DB 설명, security policy, ADR index, Phase 9 DoD와 CHANGELOG를 동기화한다. API/DB schema 변경은 없으며 DB 문서는 기존 journal이 새 registry가 아님을 구분하기 위해 수정한다. Phase 9 0/18, 다른 Phase 진행률·체크는 유지하고 실험 보고서는 필요하지 않다.

실제 storage engine/DDL/wire/TTL/OS ACL 구현, authentic commissioning/reader/writer, independent checkpoint와 backup/restore, concurrent consume/cancel 및 crash injection 검증은 미수행이다. Runtime WebAuthn·principal/binding·Recovery/Transfer·production provisioning/GENESIS/activation도 unavailable이다. IBLA authenticity 구현이 없다는 사실을 실제 설계 root의 부재와 혼동하지 않으며 운영 차단은 유지한다.

이 작업은 commit → normal push → develop 대상 Draft PR에서 종료한다. Ready/merge 및 main 변경은 금지하며 CI 실행 결과를 local docs 검증 결과와 구분한다.

## PR #195 최종 검증 — develop 전진 반영

위 Draft 검증은 최초 head 59e7316057ac37a8af66a67f1b9654f514a3cda3 당시 기록이다. 후속 요청은 모든 Gate 통과 뒤 Ready 및 expected-head guarded squash merge를 허용한다. 원격 develop은 fe2f02f0ca68bc3c4e2ccd1e8c64078b7f727379 (#196 merged)로 전진했다. upstream DohaVocal E2E 39개 파일 변경은 기존 authority/GENESIS 계약을 변경하지 않는다. 일반 merge로 이 이력을 반영하고 CHANGELOG의 두 작업 기록을 모두 보존했다. latest develop 대비 PR delta는 여전히 Markdown 13개이며 code/config/test/workflow/dependency/schema/migration delta는 모두 0이다.

현재 문서의 Draft-only 종료 표현은 새 최종 검증 범위와 분리했다. ADR-107 최초 root/commissioning·positive origin/complete coverage, stable mappings, 영구 consume-before-GENESIS, checkpoint mismatch deny, response loss/deletion/restore 이후 재사용 금지, Recovery/Transfer 분리와 private/public facts를 재감사했다. ADR-093/094 purpose, ADR-099 GENESIS deny, ADR-106 existing-only 및 runtime authentication/activation unavailable를 유지한다. checkpoint는 독립 관측/high-water evidence이고 root나 새 authorization이 아니다. 설계 순환 의존 및 관련 CURRENT contradiction은 0이며 실제 운영 구현 검증을 뜻하지 않는다.

통합 문서에서 UTF-8/fence·상대 파일 링크 551개·ADR index를 재확인했다. 검색 범위는 루트 current 문서와 docs/·planning/ 전체 334개 Markdown이며 registry/checkpoint/Recovery/Transfer 및 관련 ADR/PR 키워드를 포함한다. 기존 ADR·validation의 당시 상태는 역사 기록으로 보존한다. Phase 9는 0/18, Alembic heads는 20260918_0037 single head다. 민감 정보·private key·credential·실제 production path/data 추가는 없고 실제 production 접근은 하지 않았다.

Local Full Backend는 docs-only delta이므로 재실행하지 않는다. 기존 head의 required CI 3 SUCCESS를 새 head의 결과로 재사용하지 않으며, 새 exact head에서 세 required checks SUCCESS·reviews/threads·mergeability·D/H/main race Gate를 확인하기 전 Ready/merge하지 않는다. 병합 결과와 최종 tree equality는 PR 및 최종 보고서의 실제 결과를 따른다.

다음 선행 unit은 IBLA Commissioning / Registration Source Contract/Foundation이다. registry 첫 record의 positive origin·complete coverage와 current source authenticity·checkpoint commissioning anchor를 먼저 명확히 검증 가능한 입력으로 확립해야 한다. 그 다음 durable transactional persistence/checkpoint Foundation과 initial wire/TTL, provisioning writer 순서다. public-fact persistence만 구현할 수 있더라도 독립 source 없이 admission을 허용할 수 없다. 이번 작업에서 후속 구현은 시작하지 않는다.
