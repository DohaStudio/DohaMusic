# 오류 코드

> 문서 목적: API와 Worker의 안정적인 오류 코드를 정의한다.
> 현재 상태: **AI·Stem·Voice·Pipeline·Lyrics 구현 기준**
> Workspace v1 오류 구조: [Workspace REST API 공통 계약](workspace-rest-api-contract.md) — 공통 handler·Cursor와 Workspace·MusicProject·ProjectAsset Resource 오류 mapping 구현

`ARTIFACT_*` 공개 HTTP 오류는 [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md)에서 승인한 `[계획]` 계약이며 Router와 handler에는 아직 구현하지 않았습니다. 내부 Resolver는 안전한 전용 오류 코드를 구현했지만 공개 오류 매핑은 후속 Artifact Application Service·API 책임입니다.

| 코드 | 의미 |
|---|---|
| `INVALID_INPUT` | API 요청 형식 또는 범위 오류 |
| `INVALID_CURSOR` | 형식·서명·version·Resource·filter·정렬·위치·limit가 유효하지 않은 Cursor |
| `INVALID_LIMIT` | Cursor page limit이 1~100 범위를 벗어남 |
| `CURSOR_CONFIGURATION_ERROR` | 전용 Cursor 서명 키가 없거나 32바이트 미만인 서버 설정 오류 |
| `WORKSPACE_BOOTSTRAP_REQUIRED` | 기본 Workspace가 없어 명시적 Bootstrap 필요 |
| `WORKSPACE_NOT_FOUND` | 요청한 Workspace가 없거나 Soft Delete됨 |
| `WORKSPACE_NAME_CONFLICT` | 같은 owner 범위에서 Workspace 이름 충돌 |
| `PROJECT_NOT_FOUND` | 요청한 MusicProject가 없거나 Soft Delete됨 |
| `PROJECT_TITLE_CONFLICT` | 같은 Workspace 범위에서 MusicProject 제목 충돌 |
| `ASSET_NOT_FOUND` | 요청한 Asset이 없거나 Soft Delete됨 |
| `ASSET_CONFLICT` | Asset 생성 또는 변경 요청이 현재 상태와 충돌함 |
| `ASSET_VERSION_NOT_FOUND` | 요청한 AssetVersion이 없거나 URL의 Asset에 속하지 않음 |
| `ARTIFACT_NOT_FOUND` | Artifact가 없거나 요청 Owner에게 존재를 공개할 수 없음 |
| `ARTIFACT_CONTENT_UNAVAILABLE` | Catalog·Payload 누락 또는 delivery 정책상 안전하게 제공할 수 없음 |
| `ARTIFACT_QUARANTINED` | Artifact가 격리 상태여서 content·download 불가 |
| `ARTIFACT_GONE` | Artifact가 만료·삭제 대기·물리 삭제 상태임 |
| `ARTIFACT_INTEGRITY_ERROR` | 실제 Payload의 크기 또는 checksum이 등록 Metadata와 불일치 |
| `ASSET_VERSION_CONFLICT` | AssetVersion 번호 또는 불변 생성 계약이 기존 상태와 충돌함 |
| `PROJECT_ASSET_NOT_FOUND` | 요청한 ProjectAsset 관계가 없거나 Soft Delete됨 |
| `PROJECT_ASSET_CONFLICT` | 같은 Project와 Asset의 활성 관계가 이미 존재함 |
| `INVALID_STATE` | 현재 Resource 상태에서 요청을 수행할 수 없음 |
| `INVALID_KPOP_PRESET` | 지원하지 않는 K-POP Preset |
| `INVALID_REQUESTED_BPM` | 70~180 범위를 벗어난 목표 BPM |
| `INVALID_LANGUAGE_RATIO` | 한국어·영어 비율 범위 또는 합계 오류 |
| `INVALID_HOOK_OPTIONS` | Hook 문구·방식·반복 횟수 오류 |
| `INVALID_VOCAL_ENERGY` | 허용되지 않은 보컬 에너지 |
| `INVALID_CONCEPT` | Concept 길이·제어문자 오류 |
| `INVALID_GENERATION_OPTIONS` | 알 수 없는 Structured Option 등 K-POP 설정 오류 |
| `PRESET_GENRE_MISMATCH` | Preset canonical genre와 요청 genre 불일치 |
| `INVALID_KPOP_PROMPT` | 모방 방지 또는 컴파일 길이 제한 위반 |
| `RESOURCE_NOT_FOUND` | Job 또는 음성 프로필 없음 |
| `INTERNAL_ERROR` | 처리되지 않은 API 내부 예외 |
| `MOCK_GENERATION_FAILED` | Mock 생성 실패 |
| `AI_PROVIDER_NOT_CONFIGURED` | 알 수 없는 Provider 설정 |
| `AI_DEPENDENCY_NOT_INSTALLED` | 격리 런타임 또는 runner 없음 |
| `AI_MODEL_NOT_FOUND` | checkout·checkpoint·모델 없음 |
| `AI_MODEL_LOAD_FAILED` | 모델 초기화 실패 |
| `AI_INFERENCE_FAILED` | 추론 또는 runner 응답 실패 |
| `AI_OUT_OF_MEMORY` | CUDA 메모리 부족 |
| `AI_OUTPUT_NOT_CREATED` | 결과 오디오 없음 |
| `AI_AUDIO_DECODE_FAILED` | 생성 파일을 WAV로 해석할 수 없음 |
| `AI_TIMEOUT` | AI subprocess 제한 시간 초과 |
| `STEM_PROVIDER_NOT_CONFIGURED` | 알 수 없거나 불완전한 Stem Provider 설정 |
| `STEM_DEPENDENCY_NOT_INSTALLED` | Demucs 격리 Python 또는 runner 없음 |
| `STEM_MODEL_NOT_FOUND` | HTDemucs cache·checkpoint 없음 |
| `STEM_MODEL_LOAD_FAILED` | Demucs 모델 초기화 실패 |
| `STEM_SEPARATION_FAILED` | 분리 또는 runner 응답 실패 |
| `STEM_OUT_OF_MEMORY` | Stem 추론 중 CUDA 메모리 부족 |
| `STEM_OUTPUT_NOT_CREATED` | vocals 또는 instrumental 생성 실패 |
| `STEM_AUDIO_DECODE_FAILED` | 입력 오디오 디코딩 실패 |
| `STEM_TIMEOUT` | Stem subprocess 제한 시간 초과 |
| `LYRICS_PROVIDER_NOT_SUPPORTED` | 지원하지 않는 Lyrics Provider 시작 설정 |
| `LYRICS_GENERATION_FAILED` | Lyrics Provider 실행 실패 |
| `LYRICS_OUTPUT_INVALID` | Provider 결과 구조 검증 실패 |
| `LYRICS_VALIDATION_FAILED` | 직접 가사 검증을 진행할 수 없는 입력 |
| `PIPELINE_NOT_FOUND` | Pipeline Job 없음 |
| `PIPELINE_JOB_NOT_FOUND` | Cancel·Retry 대상 Pipeline Job 없음 |
| `PIPELINE_CANCEL_NOT_ALLOWED` | 완료·실패 상태에서 취소 요청 |
| `PIPELINE_RETRY_NOT_ALLOWED` | 실패·취소 외 상태에서 Retry 요청 |
| `PIPELINE_RETRY_INPUT_MISSING` | 원본 입력 스냅샷 검증 실패 |
| `RETRY_VOICE_PROFILE_UNAVAILABLE` | 원본 Voice Profile 없음·비활성·동의 무효 |
| `FILE_NOT_FOUND` | 결과 File 없음 |
| `FILE_JOB_MISMATCH` | File이 요청한 Pipeline에 속하지 않음 |
| `PIPELINE_NOT_COMPLETED` | 완료 전 결과 파일 접근 요청 |
| `FILE_CONTENT_UNAVAILABLE` | 재생 capability가 없는 파일 |
| `FILE_DOWNLOAD_UNAVAILABLE` | 다운로드 capability가 없는 파일 |
| `FILE_PATH_INVALID` | Storage 경계를 벗어나거나 symlink인 경로 |
| `FILE_MISSING_FROM_STORAGE` | DB 기록에 대응하는 regular file 없음 |
| `UNSUPPORTED_AUDIO_FILE` | 허용되지 않은 type·MIME·확장자·WAV header |
| `INVALID_RANGE` | 지원하지 않거나 만족할 수 없는 byte Range |
| `AUDIO_ANALYSIS_DECODE_FAILED` | final WAV decode 실패, Pipeline은 `COMPLETED` 유지 |
| `AUDIO_ANALYSIS_UNSUPPORTED` | 지원하지 않는 WAV 형식·채널 |
| `AUDIO_ANALYSIS_LUFS_UNAVAILABLE` | Integrated LUFS 계산 불가, quality는 `PARTIAL` |
| `AUDIO_ANALYSIS_INTERNAL_ERROR` | 안전한 분석 실패, Pipeline·final WAV 영향 없음 |
| `VOICE_CONSENT_REQUIRED` | Voice upload 동의 누락 또는 false |
| `VOICE_FILE_REQUIRED` | multipart 음성 파일 누락 |
| `VOICE_FILE_EMPTY` | 빈 음성 파일 |
| `VOICE_FILE_TOO_LARGE` | 25MB 초과 파일 |
| `VOICE_FILE_TOO_SHORT` | 5초 미만 WAV |
| `VOICE_FILE_TOO_LONG` | 60초 초과 WAV |
| `VOICE_FILE_TYPE_UNSUPPORTED` | WAV 확장자·MIME 불일치 |
| `VOICE_FILE_DECODE_FAILED` | 손상되거나 decode 불가능한 WAV |
| `VOICE_REFERENCE_INVALID` | sample rate·channel·PCM 계약 위반 |
| `VOICE_PROFILE_NOT_FOUND` | Voice Profile 없음 |
| `VOICE_PROFILE_IN_USE` | Pipeline·Voice Job이 참조해 삭제 차단 |
| `VOICE_STORAGE_WRITE_FAILED` | 안전한 Voice 저장 실패 |
| `VOICE_STORAGE_DELETE_FAILED` | 관리 Voice 파일 삭제 실패 |

기존 `/api` 오류는 `{ "error": { "code", "message" } }` 형식을 유지합니다. `/api/v1`은 `error_code`, `message`, `details`, `request_id`를 사용합니다. Audio Analysis 오류는 기본 API 실패가 아니라 `audio_analysis.analysis_status`와 safe warning으로 표시하며 Pipeline Job을 `FAILED`로 바꾸지 않습니다. 내부 스택·로컬 절대 경로·prompt·lyrics는 응답에 노출하지 않습니다.
# External Lyrics 오류

`LYRICS_API_KEY_MISSING`, `LYRICS_PROVIDER_NOT_SUPPORTED`, `LYRICS_PROVIDER_UNAVAILABLE`, `LYRICS_RATE_LIMITED`, `LYRICS_TIMEOUT`, `LYRICS_AUTHENTICATION_FAILED`, `LYRICS_REQUEST_REJECTED`, `LYRICS_OUTPUT_INVALID`, `LYRICS_CONTENT_BLOCKED`, `LYRICS_COST_LIMIT_EXCEEDED`, `LYRICS_REVISION_FAILED`를 구분한다. Provider 원문 body·request ID·인증 정보는 응답에 노출하지 않는다.
