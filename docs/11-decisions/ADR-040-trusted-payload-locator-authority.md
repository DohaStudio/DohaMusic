# ADR-040 — Trusted Payload Locator Authority

- 상태: Accepted
- 결정일: 2026-08-21
- 범위: DohaMusic internal runtime payload handoff Foundation

## 배경

Provider Result trust gate는 metadata-only 결과를 Workspace authority와 대조하지만 실제 Payload를 만들지 않는다. 기존 Completion은 DohaMusic이 신뢰하는 `temporary_path`를 요구하므로 Provider path·URI를 그대로 전달하지 않으면서 staging payload identity를 넘길 내부 경계가 필요하다.

## 결정

`TrustedPayloadReference`는 Provider가 아니라 DohaMusic runtime만 발급한다. `payloadref:v1:<opaque-id>`는 path semantic이 없는 versioned locator이며, registry에 immutable하게 결합된 locator만 `TrustedPayloadResolver`가 DohaMusic-owned trusted staging regular file로 해석한다. 발급과 resolve에서 root containment, canonical path, symlink/reparse escape, file identity, size, actual-byte SHA-256과 media type, 선택적 expiry를 fail-closed 검증한다.

Provider URL·path·credential, metadata descriptor checksum과 Provider artifact identity는 payload authority가 아니다. resolver는 DB transaction과 cleanup을 소유하지 않고 `ProviderOutput` adapter도 이번 결정에 포함하지 않는다.

## 결과

- 내부 locator가 경로와 storage topology를 노출하지 않는다.
- payload 변경·교체·삭제와 만료는 안전하게 거부된다.
- 기존 `ProviderOutput.temporary_path`와 Artifact ingestion의 byte-derived 무결성 계약을 보존한다.
- Foundation 구현은 deterministic process-local in-memory registry다. restart·multi-process handoff가 필요한 production wiring 전에는 durable registry와 lifecycle을 별도 결정해야 한다.
- Public API, Alembic, network/downloader, Worker wiring, 실제 ingestion은 추가하지 않는다.

## 대안

Provider path/URI 직접 전달은 authority와 SSRF/path escape 경계를 위반해 기각했다. raw UUID만 전달하는 방식은 namespace/version 진화를 표현하지 못해 기각했다. 이번 단계에서 DB persistence를 추가하는 방식은 production process와 lifecycle이 확정되지 않아 보류했다.
