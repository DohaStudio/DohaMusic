# Product/Deployment Bootstrap Authority Decision 검증

> 상태: [docs-only 검증 — runtime 미검증]
> 최종 수정일: 2026-09-18
> 기준: develop `6778ab22e69fbce54bc232815721b01413426dde`, main `63633d462043ad3ba78fee92473d19e90c361431`
> 관련 문서: [ADR-076](../11-decisions/ADR-076-product-deployment-bootstrap-authority.md), [Architecture](../03-architecture/product-deployment-bootstrap-authority.md)

## Decision completeness

External root은 명시 human designation/수락 및 governance provenance로 닫는다. pinned verifier + Ed25519/JCS signed exact approval, root key lifecycle, random installation ID/private proof, stable custodian deployment reference/proof, claim expiry/scope, one-time seal, rotation, clone/restore trusted-local boundary, runtime non-authority 및 SCHEMA_CHANGE_REQUIRED를 결정했다. 이것은 새 사용자 설계 권한의 Decision 제안이지 기존 repository에서 operational authority를 발견한 결과가 아니다.

0037 single Alembic head와 clean 전용 worktree에서 시작했다. #161/#160/#159는 MERGED, #130은 OPEN/Draft였으며 source branch/PR를 수정하지 않는다. ADR 번호는 기존 001~075를 실측해 076을 사용한다. ADR-038/042/075 본문은 수정하지 않는다. Master/실행 Roadmap의 Rights persistence 상태를 #161 merged 기준으로 정합화하되 Phase/DoD 체크·진행률은 변경하지 않는다. README/Phase DoD/DB 설계는 production 변화가 없어 수정하지 않는다. CHANGELOG의 Unreleased에 docs-only 경계를 기록한다.

## 검증 범위

git diff --check PASS. changed Markdown 11개 strict UTF-8/replacement-character/fence pairs PASS, relative links 355개 PASS. ADR 파일 76개 번호 중복 0/index 등록 PASS. docs-only allowlist 및 ADR-038/042/075·backend/frontend/ai_worker·DoD/README 무변경 PASS. added-content secret/local-path scan 및 authority/status contradiction 검토 PASS. RFC 8032/8785 primary references를 확인했으며 RFC 예제 crypto를 production 구현으로 복사하지 않는다. LF→CRLF Git 경고는 저장소 설정에 따른 normalization 안내이고 diff-check 오류는 아니다.

Production/Test/Migration/API/Frontend/Worker/Auth implementation 변경 0. 테스트 suite·실제 signature/OS private-store/anti-clone/rollback 실험 실행 0. 실제 root key/credential/approval artifact·real principal·custodian 등록 0. Production/User DB·Provider·음성/weights 접근 0. Ready/merge/CI retrigger 0. source head Alembic은 20260918_0037 유지한다.

## 한계·후속 Gate

External journal과 DB는 분산 atomicity가 없으므로 seal-first 실패는 availability를 포기한다. complete private-key/journal rollback 또는 local privileged compromise에 대한 완전한 anti-rollback은 미보장이고 out-of-bound다. 외부 journal durability/restore lineage, signature/JCS vectors, lifecycle, wrong-scope attacks, expiry, double consume, seal crash 및 production Fake 금지의 executable evidence 전 운영 활성화 금지다. 이번 PR의 completeness 판정은 PRODUCT_DEPLOYMENT_BOOTSTRAP_SCHEMA_REQUIRED_BUT_RESOLVED이며 Draft 상태에서 별도 Final Validation을 기다린다. 다음 작업은 계약 merge 후 Installation/Bootstrap Persistence Foundation; recovery/transfer/Evidence/Writer는 별도 계약이다.
