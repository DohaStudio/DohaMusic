# ADR-070: Provider 실행 identity와 submit 응답 손실 복구

> 상태: 승인
> 작성일: 2026-09-11
> 최종 수정일: 2026-09-11

## 배경

외부 Provider가 요청을 수락한 뒤 응답이 손실되면 기존 `ProviderJobBinding`만으로는 생성된 원격 실행을 복구할 수 없다.

## 결정

Music Director는 Job당 하나의 `MusicDirectorProviderExecution`을 사용한다. 네트워크 submit 전에 `INTENDED` row와 server-generated `client_execution_key`를 커밋한다. Provider는 같은 client key의 반복 submit을 하나의 원격 실행으로 수렴시켜야 한다. 반환된 external job ID는 별도 transaction에서 CAS로 한 번만 결합한다.

기존 `ProviderJobBinding.provider_job_id`는 provider가 확정한 외부 identity라는 의미를 유지한다. 첫 Foundation에서는 확정 실패 후 같은 Job 내부 재시도를 지원하지 않고 새 Job을 요구하며, 같은 Job의 Provider 전환도 금지한다.

외부 identity 불일치나 모호한 복구는 덮어쓰지 않고 `RECONCILIATION_REQUIRED`로 fail-closed한다. claim은 mutation 권한일 뿐 execution identity가 아니며 client key, claim token, Provider credential은 public API에 노출하지 않는다.

## Downgrade

복구 authority row가 존재하면 `0034 -> 0033` downgrade를 차단한다. 자동 삭제로 원격 실행 lineage를 잃지 않는다.

## 후속 작업

Provider port와 Mock Provider는 동일 client key 반복 submit의 remote cardinality `1`을 증명해야 한다.
