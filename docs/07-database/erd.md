# ERD

> 문서 목적: Phase 1 실제 DB 엔터티와 관계를 표현한다.
> 현재 상태: **Alembic 마이그레이션 구현 완료**

```mermaid
erDiagram
  GENERATION_JOBS ||--o{ GENERATED_FILES : produces

  GENERATION_JOBS {
    string id PK
    string status
    text prompt
    text lyrics
    string genre
    int duration_seconds
    int seed
    string current_step
    string error_code
    text error_message
    datetime created_at
    datetime updated_at
    datetime completed_at
  }

  GENERATED_FILES {
    string id PK
    string job_id FK
    string file_type
    string file_path
    string mime_type
    datetime created_at
  }

  VOICE_PROFILES {
    string id PK
    string name
    string reference_file_path
    boolean consent_confirmed
    datetime created_at
    datetime updated_at
  }
```

`generated_files.job_id`는 `generation_jobs.id`를 참조하고 삭제 시 함께 제거된다. `voice_profiles`는 Phase 1에서 생성 Job과 연결하지 않으며 실제 음성 처리에도 사용하지 않는다.

세부 필드는 [테이블 정의](table-definition.md), 상태 전이는 [작업 상태 모델](job-state-model.md)을 따른다.
