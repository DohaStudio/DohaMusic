# 메타데이터 스키마

> 문서 목적: 오디오와 생성 이력의 최소 메타데이터 계약을 정의한다.
> 현재 상태: **논리 스키마 초안**
> 최종 수정일: 2026-08-05

공통 필드: `id`, `owner_user_id`, `created_at`, `updated_at`, `status`. 파일은 `storage_key`, `sha256`, `mime_type`, `size_bytes`, `duration_ms`, `sample_rate_hz`, `channels`를 가진다.

생성 provenance는 prompt, lyrics, duration, BPM, seed, 모델명·버전·가중치 식별자, 파이프라인 버전, 단계별 입력/출력 파일 ID와 오류를 포함한다. 민감한 원문과 로그는 접근 범위를 구분하고 비밀 값은 기록하지 않는다.

DohaLM 가사 공동 창작 확장은 사용자 입력, AI 최초 생성본, AI 수정 제안, 사용자 수정본과 최종 승인본을 별도 version으로 식별한다. 각 AI 호출에는 Provider, 모델명·버전, manifest ID/hash, 생성 설정, 보호된 prompt 참조 또는 hash, license review ID·판정 상태와 생성 시각을 연결한다. 최종 승인에는 승인 version ID·content hash·승인 시각·철회 상태를 기록하고 음악 생성 Job은 승인 snapshot을 보존한다. 상세 계획은 [가사 버전·승인 데이터 모델](../07-database/lyrics-versioning-data-model.md)을 따른다.

DB 매핑은 [테이블 정의](../07-database/table-definition.md)를 따른다.
