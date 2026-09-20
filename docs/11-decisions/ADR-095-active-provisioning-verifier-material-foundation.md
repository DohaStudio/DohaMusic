# ADR-095: Active Provisioning Verifier Material Foundation

> 상태: 채택 — #182 merged, 운영 비활성
> 작성/최종 수정일: 2026-09-20
> 기준 develop: `0d5478859075122e472124ac19a7458139b6144e` (#181 squash merge)
> 관련: [ADR-093](ADR-093-scoped-provisioning-authority-verification-foundation.md), [ADR-094](ADR-094-authenticated-scoped-provisioning-authority-source-foundation.md), [ADR-090](ADR-090-original-confirmation-canonical-payload-foundation.md), [검증](../10-operations/active-provisioning-verifier-material-validation.md)

## 결정

ADR-094의 authenticated held authority source가 계산한 ACTIVE verifier ID/fingerprint를 실제 Ed25519 public verifier bytes와 연결하는 최소 Foundation을 채택한다. `provisioning-verifier-material-v1.json` 고정 파일은 authority/designation과 다른 physical identity, 동일 trusted root·owner·protected DACL을 가져야 한다. 기존 authority source handle, designation/pin, Windows serialization lease와 caller transaction이 모두 살아 있을 때만 same-handle로 읽고 다시 검증한다.

별도 B인 raw material reader만 구현하면 “파일에 public bytes가 있다”는 사실을 authority로 오인할 수 있다. 따라서 source/custody reader와 ACTIVE lifecycle binding을 한 coherent unit으로 묶는다. Original Confirmation signature 검증은 이 결과를 소비하는 다음 Foundation으로 분리한다.

## Exact material 계약

Schema는 `dohamusic/scoped-provisioning-verifier-material/v1`, algorithm은 `Ed25519`다. material ID/revision, authority source ID, authorization ID/revision/head, exact installation/producer/purpose/confirmation domain, verifier key ID/fingerprint와 canonical base64url public key 32 bytes를 포함한다. 전체 파일은 canonical JCS 16 KiB 이하이며 unknown/missing/duplicate key, malformed UTF-8/base64, bool·float revision을 거부한다.

모든 authority 필드는 caller가 조립한 값이 아니라 held ADR-094 record의 ADR-093 receipt 및 독립 exact expectation과 일치해야 한다. Public key SHA-256은 ACTIVE fingerprint와 일치해야 한다. superseded/revoked/old key, wrong purpose/domain/producer/installation, source/head/revision mismatch와 material substitution은 fail closed다.

## TOCTOU와 수명

순서는 `authority source revalidate → material snapshot/custody → exact parse/fingerprint → authority source revalidate → same-handle material reread → opaque held handle`이다. 후속 handoff에서도 동일 검증을 반복한다. rotate/revoke/source 변경, material replacement, transaction/lease/parent handle 변경 또는 I/O·cleanup 불확실성은 material과 parent attempt를 영구 abandon하며 값 복원이나 old-key fallback을 허용하지 않는다.

## 비권한 경계

Public verifier material은 private key나 signer가 아니다. ACTIVE authority + exact material도 Original Confirmation authenticity, source completeness의 미래 변화, CurrentnessWitness, admission, workspace/owner/Rights 권한을 증명하지 않는다. 실제 production key/credential/provisioning/ceremony, production port, schema/migration/Repository commit은 추가하지 않는다.

## 후속 dependency

후속 [ADR-096](ADR-096-original-confirmation-authenticity-foundation.md)은 이 opaque ACTIVE material을 기존 canonical Original Confirmation payload와 고정 confirmation signing domain의 Ed25519 signature 검증에 결합한다. 그 결과도 currentness witness나 admission이 아니다.
