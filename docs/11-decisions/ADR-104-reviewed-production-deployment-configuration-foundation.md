# ADR-104: Reviewed Production Deployment Configuration Foundation

> 상태: [제안 — Foundation 구현, production activation 비활성]
> 작성일: 2026-09-22
> 기준 develop: `758a0ba84460da2950e3b976301565afc3422a5c` (#190 squash merge)
> 관련 결정: [ADR-087](ADR-087-custody-policy-provisioning-initializer-provenance-contract.md), [ADR-103](ADR-103-durable-admission-production-composition-foundation.md)
> 검증: [Production Configuration 검증](../10-operations/production-deployment-configuration-validation.md)

## 결정

Production Activation의 다음 최소 prerequisite로 strict reviewed configuration bytes와 independently reviewed identity expectations를 exact 비교하는 Foundation을 둔다. Configuration은 `production` environment와 고정 profile/version, installation/deployment, authority source, verifier material, original confirmation, live lineage, external journal, authentication provider의 logical identity 및 고정 input location만 지정한다.

Wire는 bounded canonical JCS JSON이다. duplicate/unknown/missing field, float·bool/int 혼동, noncanonical UTF-8, wrong identity/environment/profile/domain/schema/file name, relative·UNC·device·ADS·dot traversal·reserved/test/Fake path, private root와 journal containment를 모두 거부한다. Windows local absolute path와 fixed filenames만 허용하고 external journal은 private source tree와 분리한다.

## Authority와 경계

Configuration 존재·parse 성공은 source authenticity, custody/ACL, native identity, installation ownership, verifier eligibility, confirmation authenticity, lineage currentness, journal identity/readiness, authenticated principal 또는 admission authority가 아니다. 모든 identity는 별도 `ProductionDeploymentExpectations`와 exact 비교한다. 이 expectations도 public comparison input이며 생성 자체는 authority가 아니다.

Path parser는 lexical routing만 검증한다. Junction/reparse·same-handle·ACL·source replacement는 config parse 시 path를 열어 추측하지 않고 기존 `_WindowsFactFiles`/custody source factory가 각 component를 handle로 열 때 거부해야 한다. External journal path도 파일을 생성하거나 migration/repair하지 않는다. Journal factory가 기존 independently provisioned schema/version/identity를 확인하는 후속 Foundation이다.

Authentication provider ID와 고정 proof model/mechanism은 routing expectation일 뿐 principal, owner, reviewer 또는 provisioning authority가 아니다. 현재 concrete production adapter는 계속 unavailable이며 Fake/test provider를 production input으로 대체하지 않는다.

## Lifetime과 비목표

Parsed configuration은 immutable application-root input이고 secret/key/credential/handle/Session을 소유하지 않는다. Private handle, journal connection/Session, authentication context, ceremony scope의 생성·cleanup은 후속 factories와 composition owner 책임이다.

이번 Foundation은 env/request auto-discovery, startup/Worker/API wiring, private source factory, external journal factory, authentication adapter, actual activation, schema/migration을 추가하지 않는다. `UnavailableProductionAdmissionComposition`은 production 기본값으로 유지한다. 다음 dependency는 이 exact config를 받아 기존 custody/source chain을 구성하되 config path를 authority로 취급하지 않는 Production Private Authority Source Factory다.
