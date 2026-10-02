# 배포 아키텍처

> Bootstrap Decision 채택(2026-09-18): #162 merged [ADR-076](../11-decisions/ADR-076-product-deployment-bootstrap-authority.md)의 external human designation, separately pinned verifier, signed exact approval과 one-time seal-first bootstrap을 정의했다. 이는 기존 reviewer 권한 확대 또는 운영 활성화가 아니다. [Bootstrap architecture](product-deployment-bootstrap-authority.md)와 #163 merged [issuance-integrity verifier Foundation](bootstrap-issuance-integrity-verifier.md)을 따른다. trusted provisioning/current status/persistence/WebAuthn/principal/binding과 실제 deployment ceremony는 미구현/미수행이다.

> 문서 목적: 개발·향후 운영 환경의 배치 경계와 비밀·GPU 요구를 정의한다.
> 현재 상태: **향후 설계 / 배포 미실행**

초기 로컬 환경은 Web, API, Worker, Database, Audio Storage를 한 개발 머신에 둘 수 있으나 프로세스와 설정은 분리한다. Worker만 GPU에 접근한다. 운영 전환 시 API/Worker 분리, 객체 저장소, 관리형 DB, Redis 큐, TLS, 중앙 비밀 저장소와 모니터링을 검토한다.

이번 단계에는 컨테이너 실행이나 운영 배포가 포함되지 않는다. 운영 절차는 [배포 가이드](../10-operations/deployment-guide.md)에 승인 게이트로 기록한다.

## Authentication topology

CURRENT 제품 배치는 `LOCAL_ONLY`이고 product login은 없다. 이는 localhost, 같은 OS 사용자 또는 같은 프로세스를 인증 증명으로 인정한다는 뜻이 아니다.

V1 production은 product-owner authority에 따라 `LOCAL_ONLY`이고 future `REMOTE_SERVICE`·`HYBRID` 가능성은 별도 미확정이다. V1은 일반 product login 없이 external identity network에 의존하지 않는 offline-capable reviewer authentication을 요구한다. DohaMusic Frontend와 일반 Workspace client는 배치와 무관하게 DohaAudio를 직접 호출하지 않고 Orchestrator를 거친다. `LOCAL_INTERNAL_SERVICE_IDENTITY`와 OS-bound human reviewer credential·delegated assertion은 별도 principal·credential이어야 한다. 상세 권위와 구현 차단 조건은 [Reviewer Authentication 배포 권위](../09-security/reviewer-authentication-deployment-authority.md)를 따른다.

Local operator proof의 concrete mechanism은 `WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL`로 선택했다. `backend.authentication`에는 provider-independent 계약과 fail-closed bootstrap만 있으며 Win32 WebAuthn adapter는 미구현이다. 따라서 `CONCRETE_OS_ADAPTER_SELECTED=true`여도 `CONCRETE_OS_ADAPTER_IMPLEMENTED=false`, `LOCAL_OPERATOR_AUTH_CONFIGURED=false`, `LOCAL_OPERATOR_AUTH_OPERATIONAL=false`다. localhost binding, process ownership과 OS username은 proof로 승격하지 않는다.

## IBLA 독립 authority 배치 계약

[ADR-108](../11-decisions/ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md)은 Anchor / Complete-Coverage Ledger / Independent Checkpoint Contract를 DECIDED한 설계 결정이다. 검토·병합 상태는 [PR #197](https://github.com/DohaStudio/DohaMusic/pull/197)을 따른다. [ADR-109](../11-decisions/ADR-109-ibla-ledger-independent-checkpoint-persistence-foundation.md)의 L/H Persistence Foundation public mechanics를 구현·검증했다. 검토·병합 상태는 [PR #198](https://github.com/DohaStudio/DohaMusic/pull/198)을 따른다. Source Verifier/Capability → Initial Authorization → Provisioning/GENESIS는 계속 NOT IMPLEMENTED다. 독립 운영 custody·commissioning/authentication/activation은 unavailable다. Anchor와 current high-water keeper는 governance custody, Ledger는 별도 writer/restore boundary를 갖는다. 같은 Windows 머신은 가능하지만 같은 unrestricted writer process나 app backup 묶음은 독립성 증거가 아니다. signed checkpoint artifact는 live high-water source를 대체하지 않는다. 실제 배포·운영 custody·인증 구현은 없다.
