# Studio UX Flow

> 문서 상태: [완료]
> 최종 수정일: 2026-08-01
> 관련 문서: [Frontend Architecture](frontend-architecture.md), [Page Structure](page-structure.md), [Pipeline API](../06-api/pipeline-api.md)

## 전체 Flow

```mermaid
flowchart LR
  S[Studio] --> M[Music Settings]
  M --> L[Lyrics]
  L --> V[Voice]
  V --> R[Review]
  R --> G[Generation]
  G --> O[Result]
  G -->|FAILED| E[Recovery]
  E --> R
```

Desktop에서는 모든 section이 하나의 작업 공간과 timeline에 공존하며 사용자가 이전 section을 자유롭게 수정한다. Mobile에서는 같은 상태를 순차 화면으로 보여준다. Review 이후 설정을 바꾸면 기존 결과를 덮지 않고 새 Job을 시작한다.

## 1. Music Settings

- 현재 활성 필드는 `prompt`, `genre`, `duration_seconds`, `seed`와 optional `generation_options`다.
- `lyrics`와 `voice_profile_id`는 Lyrics·Voice 후속 단계에서 결합해 Review의 Pipeline 요청을 구성한다.
- instrumental 생성 옵션은 현재 Pipeline API에 없으므로 `planned/disabled` 상태다. Backend 계약이 추가되기 전까지 실제 요청에 포함하지 않으며 UI에 노출하더라도 “준비 중” 또는 비활성 기능으로만 표현한다.
- 목표 BPM과 Hook phrase는 K2 Prompt 지시이며 K3.2·K3.3은 결과의 예상 BPM과 후렴 후보 구간만 분석한다. 정밀 제어와 Chorus 확정, 고급 모델 선택은 `planned/disabled`다.
- 입력 validity와 권장 범위를 inline으로 안내한다.
- K2에서는 K-POP Dance·Easy Listening·Performance Preset과 Concept·Requested BPM·Language Ratio·Hook Style·Post-Chorus·Dance Break·Vocal Energy를 접힌 고급 설정에서 제공한다. 값은 Prompt 목표이며 실제 오디오 수치나 Section 위치를 보장하지 않는다.
- Preset과 사용자 Prompt가 충돌하면 사용자 입력을 우선하고 Review의 최종 Prompt Preview와 warning에서 확인하게 한다.

## 2. Lyrics

- 직접 작성, Lyrics Lab에서 생성한 문서 복사, 검증의 세 경로를 제공한다.
- Pipeline API는 raw `lyrics`를 받으므로 Lyrics ID 자동 연결을 주장하지 않는다.
- `POST /api/lyrics/validate` 결과의 error는 진행 차단, warning은 review에서 재확인한다.
- OpenAI revision은 서버가 해당 Provider로 설정됐을 때만 가능하며 Template에서는 미지원임을 표시한다.

## 3. Voice

- 동의된 `voice_profile_id`가 필요하다.
- Voice Profile list에서 등록된 Profile을 선택하고, 목록이 비면 `/voice`의 Guided Wizard에서 새 Profile을 등록한다. 완료된 신규 Profile은 목록 refetch 뒤 Studio 선택 ID와 이름에 즉시 반영한다.
- `/voice`는 권리·처리·임시 보관·최종 reference 동의 후 Enrollment를 만들고 MediaRecorder 또는 WAV/WebM/Ogg 파일로 최대 10개 Sample을 등록한다. 품질 경고를 명시 확인하고 대표 Sample을 선택해야 submit할 수 있다.
- `sessionStorage`에는 업로드 완료 Enrollment ID와 현재 단계만 저장하며 Blob은 메모리에만 둔다. 만료·not found에서는 복원 ID를 제거한다. 기존 단일 WAV 즉시 Profile API는 `빠른 WAV 등록`, 운영자 path create는 개발 플래그 전용이다.
- 현재 서버에 FFmpeg가 없어 WebM/Ogg 녹음은 `VOICE_NORMALIZER_UNAVAILABLE`일 수 있으며 WAV fallback을 안내한다. 실제 장치·Safari와 최종 Voice Conversion 품질은 검증하지 않았다.

## 4. Review

- prompt, genre, duration, seed, lyrics summary, voice profile ID와 미해결 warning을 한 화면에서 확인한다.
- Review에서는 Preset, 적용된 Options와 Prompt 기반이라는 한계를 확인하되 Provider 내부 옵션은 노출하지 않는다. 최종 compiler version은 생성 응답·Result metadata에서 확인한다.
- “생성 시작”은 단 하나의 primary action이다.
- 시작 전 API 제한과 Mock/선택 Provider 상태를 숨기지 않는다.

## 5. Generation

```mermaid
stateDiagram-v2
  [*] --> PENDING
  PENDING --> VALIDATING
  VALIDATING --> GENERATING
  GENERATING --> STEM_SEPARATING
  STEM_SEPARATING --> VOICE_CONVERTING
  VOICE_CONVERTING --> MIXING
  MIXING --> EXPORTING
  EXPORTING --> COMPLETED
  PENDING --> CANCELLED
  VALIDATING --> CANCEL_REQUESTED
  GENERATING --> CANCEL_REQUESTED
  STEM_SEPARATING --> CANCEL_REQUESTED
  VOICE_CONVERTING --> CANCEL_REQUESTED
  MIXING --> CANCEL_REQUESTED
  EXPORTING --> CANCEL_REQUESTED
  CANCEL_REQUESTED --> CANCELLED
  PENDING --> FAILED
  VALIDATING --> FAILED
  GENERATING --> FAILED
  STEM_SEPARATING --> FAILED
  VOICE_CONVERTING --> FAILED
  MIXING --> FAILED
  EXPORTING --> FAILED
```

- 현재 step, 전체 progress, elapsed와 연결 상태를 표시한다.
- ETA는 Backend가 제공하지 않으므로 추정값을 사실처럼 표시하지 않는다.
- 취소 가능 상태에서는 확인 Dialog 뒤 `POST /api/pipelines/{job_id}/cancel`을 호출한다. 실행 중 취소는 현재 단계가 안전하게 정리된 뒤 확정될 수 있음을 안내한다.
- network polling 실패는 Job 실패가 아니다. reconnect 후 동일 job ID를 조회한다.

## 6. Result

- artwork placeholder, 제목, duration, provider/model/seed와 audio quality metadata를 표시한다.
- `GET /api/pipelines/{job_id}/files`의 metadata를 file inventory로 보여준다.
- 완료 결과는 capability가 있는 WAV만 Player와 Download를 활성화하고, 사용할 수 없는 파일은 이유를 숨기지 않고 disabled로 표시한다.
- Voice 단계는 등록 목록에서 Profile을 선택하며, 목록이 비면 `/voice` upload로 안내한다. UUID 직접 입력과 서버 경로 생성은 개발 플래그에서만 보조 수단으로 제공한다.
- 실패·취소된 작업의 “같은 설정으로 다시 만들기”는 서버의 원본 Prompt·Structured Options·Seed·Voice·Project Snapshot을 검증해 새 Pipeline Job을 생성하며 기존 Job을 변경하지 않는다. 성공 Result에는 이 Retry action을 표시하지 않는다.

### K3.1 Quality·K3.2 Tempo·K3.3 Hook UX [완료]

Pipeline 결과와 분석 상태를 분리한다.

| 분석 상태 | UI 문구 | Result 재생·다운로드 |
|---|---|---|
| pending | 분석 중 | final WAV가 유효하면 가능 |
| completed | 분석 완료 | 가능 |
| partial | 일부 분석을 완료하지 못했습니다 | 가능 |
| failed/unsupported | 분석할 수 없음 | 가능 |
| 없음 | 분석 정보 없음 | 구형 Result 정책 유지 |

Result의 오디오 분석 영역은 상태, 길이, sample rate, 채널, Sample Peak dBFS, clipping, Integrated LUFS, 예상 Tempo·confidence·오차와 후렴 후보의 추정 구간·confidence를 표시한다. PARTIAL·FAILED·UNSUPPORTED는 음악 생성 실패와 구분된 설명을 제공하고 구형 Result는 fallback 문구를 사용한다. History 목록은 Hook 후보 유무만, Project 상세은 추정 구간 요약을 표시한다. “정확한 후렴” 같은 확정 표현, Preview와 True Peak는 노출하지 않는다.

## 오류·복구

| 상황 | UI | 행동 |
|---|---|---|
| 입력 오류 | field error + summary | 해당 section 이동 |
| API 4xx | inline alert | 요청 수정 |
| network | reconnect banner | 동일 Job polling 재개 |
| Job FAILED | 실패 step + safe code | Review로 돌아가 새 Job |
| 404 Job | not-found state | Studio로 이동 |
| 결과 metadata 없음 | partial result 경고 | 다시 조회, 가짜 player 금지 |

## Draft 보존

브라우저 draft 저장은 민감하지 않은 설정과 가사에 한해 사용자 동의와 보존 기간을 정의한 뒤 구현한다. 원본 음성 binary, API key, 내부 파일 경로는 저장하지 않는다. 인증 전 multi-user project 보존을 제공하지 않는다.
