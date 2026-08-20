# Voice Conversion 테이블

> 문서 상태: [완료: CURRENT Runtime]
> 문서 범위: 운영 source of truth인 Voice Conversion 2개 Table
> 최종 수정일: 2026-08-20
> migration: `20260729_0003`
> 관련 문서: [Database Overview](database-overview.md), [CURRENT Runtime ERD](erd.md), [CURRENT Runtime Core Table Definition](table-definition.md)

## `voice_conversion_jobs`

입력 `stem_files.id`, `voice_profiles.id`, 상태·현재 단계, Provider·모델, 안정된 오류, 생성·완료 시간을 저장한다. 입력 원본과 동의 provenance 보존을 위해 FK 삭제는 RESTRICT다.

## `voice_conversion_files`

Job별 `converted_voice`와 `metadata`의 Storage 상대 경로와 MIME을 저장한다. Job 삭제 시 함께 제거된다.
