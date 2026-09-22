# ADR-105: Production Private Authority Source Factory Foundation

> 상태: [제안 — Foundation 구현, sources/production activation 비활성]
> 작성일: 2026-09-23
> 기준 develop: `94351e57c37160b3688aac2895d4862a42ffb06b` (#191 squash merge)
> 관련 결정: [ADR-094](ADR-094-authenticated-scoped-provisioning-authority-source-foundation.md), [ADR-104](ADR-104-reviewed-production-deployment-configuration-foundation.md)
> 검증: [Production Private Source Factory 검증](../10-operations/production-private-source-factory-validation.md)

## 결정

Reviewed production configuration bytes를 다시 strict parse하여 production private authority chain에 필요한 exact six-role descriptor bundle로 변환한다. 역할은 designation record, private pin facts, provisioning authority history, provisioning verifier material, original confirmation, live policy lineage다. 실제 merged reader graph가 요구하지 않는 source와 external journal은 포함하지 않는다.

각 immutable internal descriptor는 configuration digest/schema/version/profile, installation/deployment UUID, role-specific expectation identity, exact private root/fixed filename/fixed path와 기존 policy/purpose/signing domain을 결합한다. Role 순서, identity와 case-normalized path는 complete하고 unique해야 한다. Designation과 pin에는 config에 없는 authority ID를 발명하지 않고 각각 deployment/installation routing identity를 사용한다.

## Filesystem과 custody 경계

Factory는 파일을 열거나 존재 여부를 검사하지 않는다. 따라서 handle/Session/context/cleanup을 소유하지 않고 cross-request capability도 만들지 않는다. `DESCRIPTORS_READY_SOURCES_UNPROVISIONED`는 routing descriptor 완성 상태일 뿐 source readiness가 아니다.

Absolute uppercase-drive ASCII Windows root, traversal/UNC/device/ADS/trailing ambiguity/test·Fake path, fixed filename과 final path length는 ADR-104 parser가 fail closed한다. Descriptor는 fixed root containment와 exact filename을 다시 결합한다. Junction/reparse/symlink, hardlink count, native file identity, owner/protected DACL, same-handle reread와 source replacement는 path 문자열로 추측하지 않는다. 기존 `_WindowsFactFiles`, `SourceCustodyPolicy` 및 custody-bound readers가 실제 open 시 검증한다.

Configuration과 descriptor 성공은 file existence, custody, provenance, cryptographic authenticity, currentness, authorization, admission 또는 activation이 아니다. Native identity/SID/DACL policy를 config/path에서 학습하거나 bool로 대체하지 않는다. Fake/test/in-memory source, empty file, default home path와 source auto-provisioning은 없다.

## Lifetime과 비목표

Bundle은 immutable application-root routing data이고 secret/private key/credential/native handle을 포함하지 않는다. 실제 source handle은 ceremony-scoped existing reader chain과 ADR-103 caller lifetime이 소유한다.

External Journal Factory, authentication adapter, startup/Worker/API, Rights integration, schema/migration 및 production activation은 변경하지 않는다. `UnavailableProductionAdmissionComposition`은 계속 기본값이다. 다음 dependency는 independently provisioned external journal의 exact identity/path/schema/session/transaction compatibility를 검증하는 Production External Journal Factory Foundation이다.
