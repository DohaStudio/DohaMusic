# 음성 프로필 API

> 문서 상태: [진행 중]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 1 음성 동의, Phase 8 Voice 등록
> 관련 문서: [보안 정책](../09-security/security-policy.md), [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md), [ADR-019](../11-decisions/ADR-019-secure-voice-profile-upload.md)

## 사용자용 Upload

`POST /api/voice-profiles/upload`은 `multipart/form-data`의 `file`, `name`, `consent_confirmed`, `consent_text_version`을 받는다. `consent_confirmed=true`가 필수이며 현재 `consent_text_version=v1`을 사용한다.

WAV(`.wav`, `audio/wav`·`audio/x-wav`)만 허용한다. 최대 25MB를 `UploadFile` 1MiB chunk로 저장하며 `Content-Length` 사전 제한과 실제 byte 제한을 모두 적용한다. RIFF/WAVE decode, 16-bit PCM, 16kHz 이상, mono/stereo, 5~60초를 통과해야 한다. RMS·silence·clipping 후보는 차단 대신 `LOW_VOLUME`, `HIGH_SILENCE_RATIO`, `POSSIBLE_CLIPPING` warning으로 반환한다. 이 검사는 음성 화자나 본인 여부를 판정하지 않는다.

파일은 `voices/references/{profile_uuid}/reference.wav`에 저장하며 원본 파일명은 경로에 쓰지 않는다. 검증 전에는 `.uploads/{uuid}.tmp`를 사용하고 검증·atomic move·DB 저장 실패 시 temp와 orphan을 정리한다.

## 개발용 경로 생성

`POST /api/voice-profiles`는 기존 개발·내부 테스트 호환 API다. `voices/references` 아래 기존 파일 경로를 받으며 Frontend에서는 `NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH=true`일 때만 낮은 우선순위의 Development 영역에 노출한다. 공개 운영 사용자 흐름으로 사용하지 않는다.

## 목록·상세·삭제

- `GET /api/voice-profiles?limit=50&offset=0`: 최신순 목록
- `GET /api/voice-profiles/{id}`: 상세 metadata
- `DELETE /api/voice-profiles/{id}`: 미사용 Profile 삭제

Public DTO는 `id`, `name`, display filename, MIME, byte size, duration, sample rate, channels, consent version, status, quality warnings, 생성·수정 시각만 반환한다. `reference_file_path`, Storage key/root, temp path와 OS 오류는 반환하지 않는다. 기존 경로 기반 Profile의 upload metadata는 `null`, warning은 빈 배열이다.

삭제 시 Pipeline 또는 Voice Conversion에서 참조 중이면 `409 VOICE_PROFILE_IN_USE`로 차단한다. Upload가 관리하는 UUID 경로는 Profile과 함께 삭제하며, legacy 운영자 배치 파일은 DB Profile만 삭제하고 공유 가능 파일을 임의 삭제하지 않는다. Storage 삭제 실패는 DB 삭제 전에 `VOICE_STORAGE_DELETE_FAILED`로 중단한다.

원본 Voice reference의 content/download API는 제공하지 않는다. 현재 인증 없는 로컬 단일 사용자 MVP이며 공개 운영 전 인증·소유권·감사·보존 기간·삭제 재시도 정책이 필요하다.

## Guided Enrollment 영향 [계획]

현재 API는 한 요청에서 단일 WAV를 검증하고 `READY` Profile까지 즉시 생성한다. 브라우저 MediaRecorder의 WebM/Ogg, 다중 sample, sample별 품질 결과, 전체 duration, Profile 설명, 사전 validation, 임시 Enrollment 상태, upload cancel·resume·idempotency와 동의 철회 API는 없다. 신규 path·field를 이 문서에서 확정하지 않으며 [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md)의 ADR·Backend 선행 결정을 따른다.
