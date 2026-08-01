# ADR-025: Voice Profile 다중 Sample과 대표 Reference 모델

> 상태: [승인]
> 작성일: 2026-08-01
> 최종 수정일: 2026-08-01
> 관련 기능: F6 Guided Voice Enrollment
> 관련 문서: [데이터 모델](../07-database/voice-enrollment-data-model.md), [Voice Enrollment API](../06-api/voice-enrollment-api.md), [ADR-019](ADR-019-secure-voice-profile-upload.md), [ADR-024](ADR-024-browser-voice-recording-server-normalization.md)
> 관련 PR: 이 ADR을 승인·구현하는 PR에서 갱신

> 구현 메모: Alembic `20260801_0010`의 Profile 1:N Sample·대표 reference·legacy backfill에 이어 다중 Sample API, 최대 10개 Service 상한, 명시적 대표 Sample submit과 최종 Storage promotion을 구현했다. Provider별 권장 sample 구성과 품질 적합성은 여전히 `[검증 필요]`다.

## Context

현재 `voice_profiles.reference_file_path`는 `NOT NULL`이고 Pipeline과 Voice Conversion은 Profile 하나에서 reference 파일 하나를 읽는다. Guided Enrollment는 기본·밝은·차분한 말하기, 음역과 짧은 무반주 노래처럼 역할이 다른 녹음을 개별 검증·교체할 필요가 있다. 녹음을 즉시 병합하면 sample별 품질·lineage·삭제 책임을 잃고, 현재 Provider에는 다중 reference 계약이 없다.

## Decision

`VoiceProfile 1:N VoiceSample`과 `VoiceProfile.active_reference_sample_id`를 도입하는 논리 모델을 선택한다. Profile은 사용자에게 보이는 목소리 단위이고 Sample은 개별 녹음·업로드와 정규화·품질·수명주기의 단위다.

- F6 API는 Enrollment·Profile당 최대 10개 sample을 자원 제한으로 둔다. 필수 prompt 수, 총 권장 길이와 말하기:노래 구성은 Provider 평가 전까지 `[검증 필요]`이며 10개 상한이 품질 권장을 의미하지 않는다.
- 각 Sample은 `enrollment_id` 또는 `voice_profile_id`에 속한다. 완료 승격 중 두 관계가 잠시 모두 존재할 수 있지만 완료 후 Enrollment 소유권과 Profile 소유권을 명확히 기록한다.
- Sample 원본은 임시이고 정규화본만 Profile에 승격한다. 공개 DTO에는 Storage key·path를 포함하지 않는다.
- Pipeline에는 계속 대표 reference 하나만 전달한다. 여러 sample을 자동 병합하거나 Provider에 배열로 전달하지 않는다.
- submit request가 `active_reference_sample_id`를 명시해야 한다. 선택 가능한 sample은 정규화·검증이 끝난 `PASS` 또는 사용자가 경고를 확인한 `WARNING`이다. `FAIL`은 선택할 수 없다.
- UI는 `기본 말하기`의 첫 `PASS`를 추천할 수 있지만 자동 확정하지 않는다. 사용자가 대표 sample을 명시적으로 확인한다.
- 대표 sample을 바꾸는 후속 API가 도입되기 전에는 생성된 Profile의 active reference를 변경하지 않는다.

### 후보 필드와 호환 필드

`VoiceProfile`은 `id`, `name`, `description`, `status`, `active_reference_sample_id`, consent version·시각, 생성·수정·삭제 metadata를 갖는다. `VoiceSample`은 source type, prompt/category, 원본 표시 metadata, 정규화 audio metadata, quality status·warning, lifecycle status, 내부 Storage key, 만료·삭제 metadata를 갖는다. 구체적인 schema 후보는 [데이터 모델](../07-database/voice-enrollment-data-model.md)에 둔다.

전환 기간에는 기존 `voice_profiles.reference_file_path`를 active Sample의 정규화 경로로 유지한다. Worker·Pipeline은 먼저 이 호환 필드를 계속 사용하고, Repository가 active Sample 관계와 path의 일치를 검증한다. 모든 소비자가 관계 기반 조회로 전환되고 rollback 기간이 끝난 뒤에만 legacy 필드 제거를 별도 ADR·migration으로 검토한다.

### 기존 데이터 backfill

기존 Profile마다 `source_type=LEGACY_REFERENCE`, `category=legacy`, `status=READY`인 VoiceSample 하나를 만든다. Sample의 normalized key는 기존 `reference_file_path`를 가리키고 Profile의 `active_reference_sample_id`를 연결한다. nullable upload metadata는 추측해 채우지 않으며 현재 값만 복사한다. legacy 운영자 배치 파일은 소유권이 불명확하므로 backfill이 파일을 이동·삭제하지 않는다.

### Phase 7 경계

F6 Sample은 Voice Conversion reference다. Phase 7 Dataset으로 자동 복사·연결·학습하지 않는다. 재사용에는 별도 학습 opt-in, Dataset eligibility, 전사·lineage, train/validation/test split, 보존·철회와 원본·전처리·cache·모델 artifact 삭제 계약이 필요하다. Pipeline provenance는 사용한 Profile과 active Sample ID를 보존하되 내부 path를 공개하지 않는다.

## Alternatives

- 기존 단일 reference 유지: Pipeline은 단순하지만 다중 녹음을 제출 전 병합해야 하고 sample별 품질·재녹음·lineage가 사라져 제외했다.
- Profile 1:N Sample: 새 DB·API가 필요하지만 개별 수명주기와 대표 선택을 보존하므로 선택했다.
- 완료 시 derived reference 생성: Provider별 병합 규칙, silence gap, level과 음질 근거가 없어 자동 생성하지 않는다.
- 대표 1개 + 보조 N개: Pipeline 호환과 다중 Sample 보존을 함께 만족하므로 선택한 1:N 모델의 active reference 규칙으로 채택했다.
- Provider별 reference builder: 향후 Adapter 확장점으로 남기되 Primary Voice Provider와 평가 기준이 없어 현재 구현 범위에서 제외한다.

## Consequences

개별 sample 교체·품질·삭제·lineage와 현재 단일 reference Pipeline을 함께 유지할 수 있다. 대신 순환 FK(`active_reference_sample_id`), submit 동시성, active Sample 삭제 차단, Storage 승격과 DB transaction 보상 처리가 필요하다. 보조 sample을 보존하는 목적과 기간은 Profile reference 품질 개선 범위로 제한하며 무기한 Dataset처럼 사용하지 않는다.

## Rollback·Migration

신규 API를 중단하고 active Sample의 호환 `reference_file_path`로 기존 Pipeline을 계속 사용한다. migration downgrade 전 신규 Profile마다 active 정규화본 하나를 기존 레이아웃으로 안전하게 export할 수 있어야 한다. 보조 sample은 사용자 동의·보존 정책에 따라 삭제하고 이를 성공으로 숨기지 않는다.

## 재검토 조건

- Primary Voice Provider가 다중 reference 또는 특정 sample 구성의 공식 계약을 제공함
- 사용자 평가에서 대표 단일 sample보다 검증된 derived reference가 유의하게 우수함
- Profile 편집·대표 변경·sample 추가 요구가 승인됨
- Phase 7 Dataset 재사용 opt-in과 lineage ADR이 승인됨
- 최대 10개 자원 상한의 부하·UX 근거가 달라짐
