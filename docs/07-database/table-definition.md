# 테이블 정의

> 문서 목적: 초기 테이블의 책임과 주요 필드를 정의한다.
> 현재 상태: **논리 스키마 초안 / 생성 전**

모든 테이블은 UUID 기본키, 생성·수정 시각을 기본으로 두며 상태가 필요한 자원은 명시적 상태를 가진다.

| 테이블 | 책임 | 주요 추가 필드 |
|---|---|---|
| `users` | 계정과 전체 상태 | status |
| `voice_profiles` | 사용자 음색 자원 | user_id, name, status |
| `voice_samples` | 원본/전처리 음성 파일 | profile_id, storage_key, sha256, status |
| `consent_records` | 동의 증적·철회 | user_id, profile_id, policy_version, scope, granted_at, revoked_at |
| `generation_requests` | 불변 입력 스냅샷 | user_id, profile_id, prompt, lyrics, bpm, seed, duration_seconds, settings_json |
| `generation_jobs` | 실행·상태·재시도 | request_id, status, progress, attempt, parent_job_id, error_code, error_message |
| `generated_tracks` | 완성 결과 메타데이터 | job_id, status, pipeline_version |
| `generated_files` | 보컬·반주·전체곡 파일 | track_id, file_type, storage_key, hash, format |
| `model_registry` | 모델명·버전·검증 | capability, name, version, artifact_id, license_status, status |
| `model_execution_logs` | 단계별 실행 provenance | job_id, model_id, stage, timings, peak_vram, settings_json, status |

경로는 논리 Storage key만 저장한다. prompt·lyrics와 오류 메시지는 민감 정보로 분류하고 접근·보존 정책을 적용한다.
