# 메타데이터 스키마

> 문서 목적: 오디오와 생성 이력의 최소 메타데이터 계약을 정의한다.
> 현재 상태: **논리 스키마 초안**

공통 필드: `id`, `owner_user_id`, `created_at`, `updated_at`, `status`. 파일은 `storage_key`, `sha256`, `mime_type`, `size_bytes`, `duration_ms`, `sample_rate_hz`, `channels`를 가진다.

생성 provenance는 prompt, lyrics, duration, BPM, seed, 모델명·버전·가중치 식별자, 파이프라인 버전, 단계별 입력/출력 파일 ID와 오류를 포함한다. 민감한 원문과 로그는 접근 범위를 구분하고 비밀 값은 기록하지 않는다.

DB 매핑은 [테이블 정의](../07-database/table-definition.md)를 따른다.
