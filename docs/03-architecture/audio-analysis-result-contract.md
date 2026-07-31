# Audio Analysis 결과·저장 계약

> 문서 상태: [완료]
> 최종 수정일: 2026-07-31
> 관련 기능: K3.0 Audio Analysis version·storage·public allowlist
> 관련 문서: [제품 정의](../02-product/k3-audio-analysis-product-definition.md), [실패 정책](audio-analysis-failure-policy.md), [Pipeline API](../06-api/pipeline-api.md), [ADR-023](../11-decisions/ADR-023-audio-analysis-and-preview-architecture.md)

## 현재 저장소와 K3 MVP 결정

현재 `pipeline_jobs.result_metadata`와 job별 `metadata.json`은 JSON이며, `pipeline_files`는 file role·상대 경로·MIME을 저장한다. 공개 Files DTO는 내부 경로를 제거하고 완료된 검증 가능 WAV에 secure content/download URL만 제공한다.

K3 MVP는 대안 A인 기존 Result metadata JSON 확장을 채택한다.

| 대안 | 장점 | 단점 | 결정 |
|---|---|---|---|
| A. 기존 Result metadata JSON | Migration 없음, Provider-neutral, 구형 Result 호환 | 검색·인덱스·history 어려움 | **K3 MVP 채택** |
| B. 별도 Audio Analysis 테이블 | 상태·버전·재분석 추적과 통계에 유리 | Migration과 수명주기 복잡도 | Re-analysis·검색 요구 시 재검토 |
| C. 최소 컬럼 + 상세 JSON | 자주 찾는 값만 인덱스 가능 | 이중 schema 동기화 | 운영 검색 요구 확인 후 검토 |

Preview는 `pipeline_files.file_type=preview` 후보로 등록하고 내부 상대 경로만 저장한다. 실제 schema·DTO·Migration은 K3.0에서 만들지 않는다.

## 버전된 내부 구조

```json
{
  "audio_analysis": {
    "audio_analysis_version": "1.0",
    "analysis_status": "completed",
    "source_file_role": "final",
    "quality": {
      "duration_seconds": 60.1,
      "sample_rate": 44100,
      "channels": 2,
      "sample_peak_dbfs": -1.2,
      "clipping_detected": false,
      "clipping_sample_count": 0,
      "clipping_ratio": 0.0,
      "integrated_lufs": -13.8,
      "true_peak_dbtp": null
    },
    "tempo": {
      "requested_bpm": 124,
      "detected_bpm": 122.6,
      "confidence": 0.78,
      "confidence_level": "medium",
      "bpm_error": -1.4,
      "absolute_bpm_error": 1.4
    },
    "structure": {
      "first_chorus_candidate_seconds": null,
      "hook_candidate": {
        "start_seconds": 42.0,
        "end_seconds": 57.0,
        "confidence": 0.63,
        "confidence_level": "medium"
      }
    },
    "preview": {
      "status": "completed",
      "file_id": "opaque-file-id",
      "start_seconds": 42.0,
      "end_seconds": 57.0,
      "duration_seconds": 15.0,
      "selection_strategy": "hook_candidate"
    },
    "warnings": [],
    "completed_at": "2026-07-31T00:00:00Z"
  }
}
```

`true_peak_dbtp`는 oversampling 기반 구현과 reference 검증 전 `null`이다. `first_chorus_candidate_seconds`와 `hook_candidate`는 추정값이다. `file_id`는 opaque ID이며 path가 아니다.

## 최소 버전 계약

- 필수: `audio_analysis_version`
- 향후 선택: `tempo_analyzer_version`, `loudness_analyzer_version`, `hook_analyzer_version`, `preview_exporter_version`
- 알고리즘, 중요 기본값 또는 calibration 변경 시 version을 올려 기존 결과와 구분한다.
- 같은 version에서 같은 WAV와 설정은 허용 오차 안에서 재현 가능해야 한다.

초기에는 컴포넌트별 version을 억지로 분리하지 않는다. 독립 배포·재분석 요구가 생길 때 추가한다.

## 공개 allowlist

| 화면/API | 공개 범위 |
|---|---|
| Pipeline Result | analysis status/version, quality, tempo, Hook/Chorus 후보, Preview capability·URL |
| History 목록 | analysis status, detected BPM·confidence 요약, Preview 가능 여부 |
| History 상세 | Result 공개 범위와 동일 |
| Project Job 목록 | status, detected BPM 요약, Preview 가능 여부 |
| Files | 기존 필드 + Preview의 opaque `file_id`, secure content/download URL |

공개 가능 값은 duration, sample rate, channels, Sample Peak, clipping, Integrated LUFS, 검증된 True Peak, detected/requested BPM 차이, confidence, Hook/Chorus 후보 시간, Preview URL, status와 version이다.

다음은 공개하지 않는다.

- 내부 절대·상대 파일 경로와 Storage root
- 실행 command, temporary path, model path
- stack trace와 raw analyzer debug data
- 전체 `result_metadata`, 내부 benchmark trace와 미검증 partial 값

공개 DTO는 nested allowlist를 별도로 생성해야 하며 내부 JSON을 그대로 직렬화하지 않는다.

## Preview storage와 수명주기

- 내부 후보 경로: `pipelines/{job_id}/preview_15s.wav`
- 저장 형식/MIME: PCM WAV / `audio/wav`
- 공개: 기존 secure content/download endpoint의 opaque URL만 제공
- cache: 현행 `private, no-store` 유지
- download: 최종 WAV와 같은 검증을 통과하면 허용
- Project 삭제: 현행 ADR-020대로 Job 연결만 해제하므로 Preview도 Job과 함께 보존
- Job/Result 삭제: 삭제 기능이 도입되면 Preview와 metadata를 같은 transaction/cleanup unit으로 제거
- Retry: 새 Job 아래 새 Preview 생성, 기존 Preview 복사 금지
- Re-analysis: 기존 WAV에서 새 Preview를 생성하되 검증 완료 전 기존 파일을 덮지 않는 atomic 교체 정책 필요

## 호환성과 무결성

구형 Result는 `audio_analysis`가 없으며 이를 `not_requested`와 동일하게 표시할 수 있다. 알 수 없는 version이나 malformed JSON은 공개하지 않고 `unavailable`로 처리한다. 분석 metadata가 없어도 final WAV row와 secure access 검증이 통과하면 재생·다운로드는 가능하다.
