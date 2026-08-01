# ADR-026: Voice Enrollment 임시 업로드와 정리 수명주기

> 상태: [제안]
> 작성일: 2026-08-01
> 최종 수정일: 2026-08-01
> 관련 기능: F6 Guided Voice Enrollment
> 관련 문서: [Voice Enrollment API](../06-api/voice-enrollment-api.md), [데이터 모델](../07-database/voice-enrollment-data-model.md), [Storage Architecture](../03-architecture/storage-architecture.md), [음성 동의 정책](../09-security/voice-consent-policy.md)
> 관련 PR: 이 ADR을 승인·구현하는 PR에서 갱신

> 구현 메모: `0010` lifecycle 기반과 `0011` hashed idempotency 저장소, 별도 임시 Storage, 24시간 sliding/7일 absolute lazy 만료, submit promotion과 즉시 cleanup primitive를 구현했다. 주기적 expiration scanner·cleanup retry scheduler와 crash 복구 worker가 없어 상태는 `[제안]`으로 유지한다.

## Context

현재 upload는 한 HTTP 요청에서 임시 파일 검증, final move, Profile 생성까지 수행한다. 여러 sample에서는 브라우저 종료, 일부 검증 실패, 취소, 중복 submit, DB·파일 이동 실패와 방치된 개인 음성을 하나의 요청으로 복구할 수 없다. 명시적 제출 전 데이터를 최종 Profile로 취급하면 불완전 Profile과 orphan이 생긴다.

## Decision

명시적 제출 전 서버 작업 단위로 `VoiceEnrollment`를 도입하고, 로컬 MVP에는 최종 reference와 분리된 `voices/enrollments` Storage root를 사용한다.

### 생성·동의·제출

- 사용자가 안내와 등록 방법을 확인하고 “등록 시작”을 명시적으로 누를 때 `POST /api/voice-enrollments`로 server-generated ID를 만든다. 페이지 진입만으로 만들지 않고 첫 upload에서 암시적으로 만들지 않는다.
- 서버는 Profile 이름·설명 draft, consent policy version과 마지막 활동 시각을 저장할 수 있다. `consent_confirmed_at`은 최종 `submit`에서 권리·목적·보존 범위를 다시 확인한 시각만 기록한다.
- 현재 로컬 MVP의 sample upload는 원본을 보관하고 threadpool에서 정규화·검증을 동기 완료해 `201`을 반환한다. 별도 durable Job·polling은 만들지 않았으며 운영 latency와 crash 복구 요구가 커지면 다시 검토한다.
- submit은 Enrollment와 eligible Sample을 잠그고 상태·동의·warning 확인·active reference를 재검증한 뒤 Profile 생성을 예약한다. 최종 Profile은 이 시점 전에는 만들지 않는다.

### 서버 상태와 UI 상태

Enrollment 서버 상태는 `DRAFT`, `READY_TO_SUBMIT`, `SUBMITTING`, `COMPLETED`, `CANCELLED`, `EXPIRED`, `DELETE_PENDING`, `DELETE_FAILED`로 제한한다. Sample 서버 상태는 `UPLOADED`, `VALIDATING`, `READY`, `FAILED`, `DELETE_PENDING`, `DELETE_FAILED`다. `ACTION_REQUIRED`는 `quality_status=WARNING`과 acknowledgement로 표현하고 별도 Enrollment enum으로 만들지 않는다.

`RECORDING`, `PAUSED`, `PREVIEWING`, `UPLOADING`, 화면 step과 network 결과 불명확은 UI 전용 상태다. UI가 서버 enum을 추측해 영속하지 않는다.

### 만료와 복원

- 기본 만료는 마지막 성공한 mutation 후 24시간의 sliding expiration이다.
- sample 추가·삭제, draft 수정, warning 확인은 만료를 연장한다. 조회, polling, 실패 요청과 passive page load는 연장하지 않는다.
- 생성 시점부터 절대 7일이 지나면 활동과 무관하게 만료한다. 개인 음성을 방치하지 않으면서 당일 중단 복원을 허용하기 위한 로컬 MVP 상한이다.
- GET으로 metadata와 상태를 복원할 수 있지만 브라우저 Web Storage에는 audio binary를 저장하지 않는다.
- 로컬 MVP upload는 요청 단위 재시도만 제공하고 byte-range/chunk resume는 제공하지 않는다. 같은 idempotency key와 동일 hash의 재요청은 기존 Sample을 반환한다.

### Idempotency와 동시성

- create, sample upload, submit은 `Idempotency-Key`를 요구한다. scope는 endpoint와 Enrollment ID이며 key·request fingerprint·result ID를 저장한다.
- 같은 key·같은 fingerprint는 기존 결과를 반환하고 같은 key·다른 fingerprint는 `409 IDEMPOTENCY_CONFLICT`다.
- Enrollment당 완료 Profile은 최대 하나라는 unique 제약을 둔다. `COMPLETED` 재submit은 기존 Profile 연결을 반환하고, 다른 active reference·metadata로 재submit하면 conflict다.
- submit은 DB row lock 또는 SQLite에서 동등한 compare-and-set 상태 전이로 직렬화한다. Sample 삭제는 active submit 또는 Profile reference로 사용 중이면 `409 VOICE_SAMPLE_IN_USE`다.

### Storage와 transaction 경계

```text
voices/enrollments/{enrollment_id}/samples/{sample_id}/original.bin
voices/enrollments/{enrollment_id}/samples/{sample_id}/normalized.wav
voices/references/{profile_id}/samples/{sample_id}/reference.wav
```

DB와 filesystem은 하나의 원자 transaction이 아니므로 staged promotion과 보상 처리를 사용한다. submit worker는 대상 path를 예약하고 normalized 파일을 final staging으로 복사·fsync·검증한 뒤 첫 DB transaction에서 Profile을 내부 `PREPARING`, Enrollment를 `SUBMITTING`으로 두고 Sample 관계와 active reference를 기록한다. commit 뒤 staging을 final 이름으로 atomic rename하고 재검증한 다음 두 번째 짧은 transaction에서 Profile `READY`와 Enrollment `COMPLETED`를 함께 확정한다. 그 뒤 원본·남은 temp 삭제를 예약한다. 파일 승격 또는 commit 후 정리가 실패하면 Profile을 `READY`로 노출하지 않고 `DELETE_PENDING`/복구 가능한 작업 상태를 남긴다. Pipeline은 Profile `READY`와 존재·경계 검사를 통과한 active reference만 사용한다.

### Cleanup 주체와 재시도

로컬 MVP는 Backend 내부 cleanup service가 시작 시와 주기적으로 만료·`DELETE_PENDING`·orphan을 scan한다. 정상 요청의 sample 삭제·cancel도 같은 idempotent cleanup service를 호출한다. DB가 source of truth이며 Storage만 존재하는 항목은 server-generated path와 grace period를 확인한 뒤 orphan 후보로 격리한다.

삭제는 bounded exponential backoff로 재시도하고 시도 횟수·마지막 안전한 오류 코드·시각을 기록한다. retry exhaustion은 `DELETE_FAILED`와 운영 경고로 남긴다. raw OS 오류, 내부 path와 원본 파일명은 공개 DTO·일반 로그에 넣지 않는다. Phase 9에서는 내구성 Queue·object storage lifecycle·audit로 교체하되 DB 상태와 중복 방지 계약을 유지한다.

### Cleanup matrix

| 이벤트 | 원본 임시 파일 | 정규화 파일 | DB Sample | Enrollment | Profile |
|---|---|---|---|---|---|
| upload/decode 검증 실패 | 삭제 예약 | 부분 출력 삭제 예약 | `FAILED`, 안전한 오류 보존 | `DRAFT` 유지 | 생성 안 함 |
| 사용자가 Sample 삭제 | 삭제 예약 | 삭제 예약 | 성공 시 삭제 tombstone, 실패 시 `DELETE_*` | 재평가 | 영향 없음 |
| Enrollment 취소 | 모두 삭제 예약 | 모두 삭제 예약 | `DELETE_PENDING` 후 tombstone | `CANCELLED` 후 정리 상태 노출 | 생성 안 함 |
| Enrollment 만료 | 모두 삭제 예약 | 모두 삭제 예약 | `DELETE_PENDING` 후 tombstone | `EXPIRED` 후 정리 상태 노출 | 생성 안 함 |
| Profile 생성 성공 | 삭제 예약 | final reference로 승격 | Profile에 연결·`READY` | `COMPLETED` | 하나 생성 |
| Profile 생성 실패 | 임시 보존 후 TTL cleanup | 임시 보존 또는 staging rollback | 기존 상태로 복구하거나 실패 기록 | 재시도 가능한 `READY_TO_SUBMIT` 또는 `DELETE_PENDING` | 불완전 Profile 제거 |
| 동의 철회 | 정책 대상 모두 삭제 작업 | Profile Sample·파생 reference 삭제 작업 | 철회·삭제 상태 추적 | draft면 cancel과 동일 | 새 사용 차단; 기존 결과 정책은 `[정책 결정 필요]` |
| Profile 삭제 | 관리 원본은 없음 | 모든 관리 Sample 삭제 | 삭제 상태 추적 | 완료 이력 최소 metadata | 사용 중이면 차단, 아니면 삭제 |

동의 철회는 권리·처리 목적을 철회하고 새 작업과 대기 작업을 막는 정책 사건이다. Enrollment cancel은 아직 Profile이 되지 않은 draft를 포기하는 사건이다. 기존 생성 결과물을 철회 시 유지할지 삭제할지는 법률·제품 판단이 필요하므로 `[정책 결정 필요]`로 남긴다. Pipeline provenance record는 음성 binary 삭제 후에도 최소 식별자·정책상 허용된 감사 metadata만 보존할 수 있다.

## Alternatives

- 기존 `voices/references/temporary`: 구현은 작지만 final reference와 retention 경계가 섞여 orphan scan이 위험해 제외했다.
- 별도 `voices/enrollments`: root 단위 cleanup과 final 승격이 명확해 로컬 MVP로 선택했다.
- 파일은 처음부터 final Storage에 두고 DB 상태로만 구분: 미완료 파일을 Worker가 참조할 위험과 삭제 범위가 커 제외했다.
- object storage lifecycle: 운영에는 적합하지만 현재 local filesystem에 과도하다. Phase 9에서 lifecycle rule만 믿지 않고 DB cleanup 상태와 함께 도입한다.

## Consequences

새로고침·부분 실패·중복 submit을 복원하고 민감 음성의 임시·최종 경계를 명확히 할 수 있다. 대신 만료 scanner, idempotency record, 상태 전이, filesystem/DB 보상과 삭제 재시도가 필요하다. 내부 ThreadPool은 crash recovery가 없으므로 구현 전 cleanup service의 시작 복구와 동시성 test가 필수다.

## Rollback·Migration

신규 Enrollment route를 비활성화하고 기존 단일 WAV upload를 유지한다. 미완료 Enrollment는 생성 차단 후 cleanup 완료를 확인한다. 이미 완료된 Profile은 ADR-025 호환 `reference_file_path`로 계속 사용할 수 있다.

## 재검토 조건

- 공개 다중 사용자 인증·소유권·quota·rate limit 도입
- 외부 Queue, 다중 Backend instance 또는 object storage 도입
- 24시간 sliding/7일 absolute 정책의 사용자 손실·보안 운영 근거 변화
- chunk resume 또는 direct-to-object-storage upload 필요
- 법률 검토로 동의 철회·기존 생성 결과·감사 metadata 정책 확정
