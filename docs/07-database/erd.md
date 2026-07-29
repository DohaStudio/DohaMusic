# ERD

```mermaid
erDiagram
  GENERATION_JOBS ||--o{ GENERATED_FILES : creates
  GENERATED_FILES ||--o{ STEM_JOBS : source
  STEM_JOBS ||--o{ STEM_FILES : creates
  STEM_FILES ||--o{ VOICE_CONVERSION_JOBS : vocal_source
  VOICE_PROFILES ||--o{ VOICE_CONVERSION_JOBS : reference
  VOICE_CONVERSION_JOBS ||--o{ VOICE_CONVERSION_FILES : creates
  VOICE_PROFILES ||--o{ PIPELINE_JOBS : reference
  PIPELINE_JOBS ||--o{ PIPELINE_FILES : creates

  GENERATION_JOBS {
    string id PK
    string status
    text prompt
    text lyrics
    string genre
    int duration_seconds
    int seed
  }
  GENERATED_FILES {
    string id PK
    string job_id FK
    string file_type
    string file_path
    string mime_type
  }
  STEM_JOBS {
    string id PK
    string source_file_id FK
    string status
    string provider
  }
  STEM_FILES {
    string id PK
    string job_id FK
    string file_type
    string file_path
  }
  VOICE_PROFILES {
    string id PK
    string name
    string reference_file_path
    boolean consent_confirmed
  }
  VOICE_CONVERSION_JOBS {
    string id PK
    string source_file_id FK
    string voice_profile_id FK
    string status
    string current_step
    string provider
    string model_name
    string model_version
    string error_code
    text error_message
    datetime created_at
    datetime updated_at
    datetime completed_at
  }
  VOICE_CONVERSION_FILES {
    string id PK
    string job_id FK
    string file_type
    string file_path
    string mime_type
    datetime created_at
  }
  PIPELINE_JOBS {
    string id PK
    string voice_profile_id FK
    string status
    string current_step
    int progress_percent
    text prompt
    text lyrics
    string genre
    int duration_seconds
    int seed
    string pipeline_version
    json result_metadata
    string failed_step
    string error_code
    text error_message
  }
  PIPELINE_FILES {
    string id PK
    string job_id FK
    string file_type
    string file_path
    string mime_type
  }
```

`voice_conversion_jobs.source_file_id`는 `stem_files` 중 `file_type=vocals`만 Service에서 허용한다. Voice Conversion과 Pipeline의 `voice_profile_id`는 동의된 profile만 허용한다. 입력 FK는 `RESTRICT`, 출력 파일은 Job 삭제 시 `CASCADE`다. migration revision은 `20260729_0004`다.
