# ADR-094: Authenticated Scoped Provisioning Authority Source Foundation

> 상태: 채택 — #181 merged, 운영 비활성
> 작성/최종 수정일: 2026-09-20
> 기준 develop: `82c19261f9b7f2074dcf6e23305b7067465ffcae` (#180 squash merge)
> 관련: [ADR-083](ADR-083-private-pin-facts-reader-foundation.md), [ADR-086](ADR-086-designation-source-custody-policy-foundation.md), [ADR-093](ADR-093-scoped-provisioning-authority-verification-foundation.md), [검증](../10-operations/authenticated-provisioning-authority-source-validation.md)

## 결정

ADR-093의 scoped authority history를 production admission chain이 읽기 위한 최소 source Foundation을 채택한다. Reviewed composition이 고정한 private root 아래 `provisioning-authority-history-v1.json`만 읽는다. 별도로 주입된 root/file physical identity, owner SID, protected exact DACL을 검증하고 기존 private pin, designation snapshot, Windows serialization lease와 caller transaction이 살아 있는 동안 같은 native handle을 유지한다.

읽기 순서는 `bounded snapshot → strict canonical source parse → ADR-093 complete-history verification → parent/source same-handle revalidation → opaque held result`이다. source의 `source_id`, revision, authorization ID, root key ID와 head event digest는 caller의 독립 exact expectation 및 검증 receipt와 모두 일치해야 한다. authority projection이 `ACTIVE`이고 current verifier ID/fingerprint가 하나 존재할 때만 held result를 만든다.

## Wire와 경계

Source schema는 `dohamusic/scoped-provisioning-authority-source/v1`이다. 필드는 schema, source ID/revision, authorization ID, root key ID, head event digest와 base64url-unpadded ADR-093 event 배열만 허용한다. canonical JCS, 1 MiB 전체 한도와 256 event 한도를 적용하며 duplicate/unknown key, float·bool revision, malformed UTF-8/base64, empty/truncated/forked history를 거부한다.

Root verifier는 source에서 self-enroll하지 않는다. 기존 custody-bound pin/designation chain의 root identity, fingerprint와 public bytes로 구성하고 source의 모든 event를 ADR-093의 고정 purpose/domain/signature/lifecycle 규칙으로 다시 검증한다. source wrapper의 존재, ACL 또는 metadata만으로 authenticity를 주장하지 않는다.

결과는 provider registry에만 존재하는 복사·직렬화 불가 opaque handle이다. 후속 handoff 때 원래 designation/pin/lease/session과 source bytes, custody 및 ADR-093 receipt를 다시 확인한다. mismatch, transaction 교체, I/O/API 불확실성은 source와 parent attempt를 영구 abandon하며 값 복원으로 재활성화하지 않는다.

## Currentness와 비권한 경계

Source currentness는 열린 동일 handle의 bytes/identity/custody가 교체되지 않았다는 뜻이다. Authority currentness는 제공된 complete signed lifecycle의 마지막 projection이 ACTIVE라는 뜻이다. 둘은 별개이며 둘 다 통과해도 외부 source completeness, root의 현재 eligibility 또는 새로운 journal head를 증명하지 않는다.

이 Foundation은 `CurrentnessWitness`, admission, Original Confirmation authenticity, live-lineage authenticity, workspace/owner/Rights 권한이나 서명 권한을 발급하지 않는다. 실제 Product/Deployment private key, credential, writer, production port, schema/migration/Repository transaction은 추가하지 않는다.

## 후속 dependency

후속 [ADR-095](ADR-095-active-provisioning-verifier-material-foundation.md)는 held authenticated authority source의 ACTIVE projection을 custody-bound exact verifier bytes와 결합한다. Original Confirmation authenticity는 그 다음 Foundation이며 authenticated source와 CurrentnessWitness, admission을 계속 분리한다.
