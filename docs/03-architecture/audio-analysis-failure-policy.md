# Audio Analysis 실패 정책

> 문서 상태: [완료]
> 최종 수정일: 2026-10-12
> 관련 기능: K3.0 계약, K3.1 Quality, K3.2 Tempo와 K3.3 Hook 실패·Cancel·Retry
> 관련 문서: [제품 정의](../02-product/k3-audio-analysis-product-definition.md), [결과 계약](audio-analysis-result-contract.md), [Pipeline Orchestrator](pipeline-orchestrator.md), [ADR-023](../11-decisions/ADR-023-audio-analysis-and-preview-architecture.md)

## 상태 계약

K3.1·K3.2·K3.3의 JSON 저장값과 공개 DTO는 다음 대문자 상태를 사용한다.

| 식별자 | 저장값 | 의미 |
|---|---|---|
| `ANALYSIS_NOT_REQUESTED` | `NOT_REQUESTED` | 분석 대상이 아니거나 기능이 꺼짐 |
| `ANALYSIS_PENDING` | `PENDING` | 최종 WAV 이후 분석 대기·실행 중 |
| `ANALYSIS_COMPLETED` | `COMPLETED` | Quality·Tempo·Hook 필수 분석이 모두 완료됨 |
| `ANALYSIS_PARTIAL` | `PARTIAL` | WAV는 유효하지만 LUFS·Tempo·Hook 중 일부가 없거나 Hook 중앙 fallback임 |
| `ANALYSIS_FAILED` | `FAILED` | 핵심 WAV 분석 결과를 신뢰할 수 없음 |
| `ANALYSIS_UNSUPPORTED` | `UNSUPPORTED` | 형식·채널·sample type이 지원 범위 밖 |

Preview는 `pending|ready|failed|unavailable`를 별도로 기록한다. 구형 결과의 필드 부재는 unavailable로 표시한다. Hook 후보 부재와 낮은 tempo confidence는 Pipeline 오류가 아니라 부분/미사용 가능한 분석 결과다.

## 실패 원인과 처리

| 원인 코드 | analysis 상태 | Pipeline 영향 | 사용자 메시지 |
|---|---|---|---|
| `source_file_missing` | failed | 없음 | 분석할 최종 파일을 찾을 수 없습니다. |
| `invalid_audio` | failed | 없음 | 오디오를 분석할 수 없습니다. |
| `unsupported_format` | unsupported | 없음 | 현재 분석을 지원하지 않는 형식입니다. |
| `decoder_failure` | failed | 없음 | 오디오 분석 준비 중 오류가 발생했습니다. |
| `insufficient_duration` | partial | 없음 | 일부 분석에는 곡 길이가 충분하지 않습니다. |
| `tempo_confidence_too_low` | partial | 없음 | 템포 신뢰도가 낮아 참고용으로만 표시합니다. |
| `hook_candidate_not_found` | partial | 없음 | 대표 Hook 후보를 찾지 못했습니다. |
| `preview_export_failure` | 분석 유지, Preview failed | 없음 | 미리듣기를 만들지 못했지만 완성곡은 사용할 수 있습니다. |
| `storage_failure` | failed 또는 Preview failed | 없음 | 분석 결과 저장에 실패했습니다. |
| `cancel_requested` | partial 또는 failed | 없음 | 분석이 취소되었습니다. |

최종 WAV가 유효하면 Result 재생·다운로드는 계속 가능하다. History와 Project는 Pipeline 상태와 함께 분석 상태를 요약하며, 분석 실패를 음악 생성 실패처럼 표시하지 않는다.

## 로그와 공개 정보

- 공개: 안전한 원인 코드, 사용자 메시지, status, version, 완료/갱신 시각
- 내부 로그: job/result ID, 단계, analyzer version, 예외 유형, elapsed, 입력 역할
- 비공개: stack trace, 내부 경로, command, 임시 경로, model path, raw debug array

민감한 Prompt·가사·음성 내용과 전체 파일 경로를 로그에 기록하지 않는다. 예외 stack은 서버 로그에만 남기고 공개 metadata에는 포함하지 않는다.

## Cancel 계약

현재 Worker는 Quality·Tempo·Hook 분석 전후의 단계 경계에서 취소를 확인한다. 장시간 analyzer 내부 cooperative check는 아직 없다.

1. 분석을 중단하고 아직 검증되지 않은 partial metric을 공개하지 않는다.
2. 유효 지표만 남길 수 있으면 `partial`, 아니면 `failed/cancel_requested`를 기록한다.
3. Preview 임시 파일은 삭제하고 등록 완료된 Preview는 정책에 따라 유지한다.
4. Final WAV 성공 경계를 통과했다면 원본 WAV와 Pipeline `COMPLETED`는 유지한다.
5. 성공 경계 전 기존 Pipeline 취소는 현행처럼 부분 산출물을 정리하고 `CANCELLED`로 끝난다.

실제 순서는 Export → Quality·Tempo·Hook → 취소 확인 → metadata·file row와 `COMPLETED`의 원자적 확정 → Preview 독립 후처리다. Tempo 또는 Hook만 실패하면 다른 유효 분석을 보존하고 aggregate를 `PARTIAL`로 둔다. Hook confidence가 `0.50` 미만이면 Preview는 중앙 fallback을 사용한다. 분석 중에는 단계 경계의 취소 확인이 적용되며 analyzer 내부의 별도 취소 API는 없다. 성공 확정 이후 취소 API는 `409`다. Preview 예외는 원본 cleanup이나 Job `FAILED` 전이에 도달하지 않는다.

Preview 등록 실패는 transaction을 rollback하고 새 파생 WAV를 정리한다. 재실행 시 이미 ready가 확정된 경우는 삭제하지 않는다. 실패 상태 DB 저장도 실패하면 기존 pending을 보존하고 startup에서 재시도한다. ready 이후 metadata.json 저장 실패는 ready와 파일을 유지하고 DB를 기준으로 재동기화한다. 모든 실패는 내부 로그에 기록한다. 복구 한계·DB write lock의 영향은 ADR-023에 기록한다.

## Retry와 재분석

- Pipeline Retry: 실패·취소된 원본 Snapshot으로 새 음악 Job과 새 WAV를 생성하고 새 분석을 수행한다. 기존 분석 결과를 복사하지 않는다.
- Re-analysis: K3.3에서도 구현하지 않으며 후속 재검토 대상이다.
- K3 MVP: 자동 1회 분석만 구현 대상으로 두며 수동 Re-analysis API와 분석 history는 후속 계획이다.
- 버전 변경: 기존 결과를 덮지 않는 것이 원칙이며, MVP JSON 확장 단계에서는 최신 결과와 이전 version 보존 전략을 구현 PR에서 확정한다.

Retry와 Re-analysis는 식별자·수명주기·비용이 다른 작업이다. 사용자 문구와 API에서 같은 “다시 시도”로 합치지 않는다.

## 복구와 Rollback

분석 기능을 비활성화하면 새 Result는 `not_requested`로 기록하거나 분석 필드를 생략한다. 기존 Result·WAV·secure content/download는 변경 없이 유지한다. 분석 장애가 반복되어도 Provider나 Mixer fallback으로 변환하지 않는다.
