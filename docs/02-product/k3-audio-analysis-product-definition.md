# K3 Audio Analysis 제품 정의

> 문서 상태: [완료]
> 최종 수정일: 2026-07-31
> 관련 기능: K3.0 Audio Analysis 계약·평가 문서
> 관련 문서: [결과 계약](../03-architecture/audio-analysis-result-contract.md), [실패 정책](../03-architecture/audio-analysis-failure-policy.md), [K-POP Roadmap](../../planning/kpop-creation-roadmap.md), [ADR-023](../11-decisions/ADR-023-audio-analysis-and-preview-architecture.md)

## 목적과 제품 경계

K3 Audio Analysis는 생성된 WAV의 기술적 품질과 음악적 특성을 후처리 단계에서 분석해 사용자에게 참고 정보를 제공하는 계층이다. 분석값은 생성 모델의 구조 준수를 보장하지 않으며 오탐·미탐·실패 가능성이 있는 측정 또는 추정 결과다. K3는 K2의 Prompt 목표를 검증할 단서를 제공하지만 Provider를 제어하거나 결과를 교정하지 않는다.

이번 K3.0은 제품·저장·실패·평가 계약만 완료한다. Audio DSP, API DTO, DB, Frontend와 Provider는 변경하지 않으며 K3.1~K3.4는 모두 `[계획]`이다.

## 값의 의미

| 값 | 분류 | 제품 표현 |
|---|---|---|
| `requested_bpm` | 사용자 요청값 | “요청 템포” |
| `detected_bpm` | 분석 추정값 | “예상 템포: 약 … BPM” |
| `duration_seconds` | 파일 측정값 | “재생 길이” |
| `sample_rate`, `channels` | 파일 측정값 | 기술 정보 |
| `sample_peak_dbfs` | sample 측정값 | “Sample Peak” |
| `integrated_lufs` | 표준 기반 측정값 | “Integrated LUFS” |
| `true_peak_dbtp` | oversampling 기반 측정값 또는 미지원 | 구현 검증 전 `planned` |
| `first_chorus_time` | 구조 추정값 | “Chorus 후보” |
| `hook_start`, `hook_end` | Hook 후보 추정값 | “Hook 후보 구간” |
| `preview_start`, `preview_end` | 제품 선택값 | Preview 선택 구간 |
| Preview WAV | 생성 산출물 | 안전한 재생용 파생 파일 |

측정값도 decoder·표준 구현·입력 상태의 영향을 받으며 음악적 품질을 보장하지 않는다. 보장값은 “검증된 파일에서 읽은 sample rate”처럼 계약과 테스트로 확인된 범위에만 사용한다.

## 분석 대상

- `primary_analysis_source`: 완료 Pipeline의 최종 믹스 `final.wav`
- `optional_analysis_sources`: `converted_voice`, `instrumental`은 K3 MVP 제외, 후속 진단 후보
- 원본 보존: 분석과 Preview는 최종 WAV를 수정하거나 덮어쓰지 않는다.
- 파일 누락: `ANALYSIS_FAILED`와 `source_file_missing`을 기록하고 기존 Result 상태는 유지한다.
- 미지원 형식: K3 MVP는 기존 secure file 경계와 같은 RIFF/WAVE만 허용하고 `ANALYSIS_UNSUPPORTED`를 기록한다.

모든 Stem을 기본 분석하지 않는다. Stem별 분석은 비용과 지표 의미를 별도로 검증한 뒤 추가한다.

## Pipeline 위치와 성공 조건

```text
Music Generation
→ Stem Separation
→ Voice Conversion
→ Mixer
→ Final WAV Export
→ Final WAV 성공 경계
→ Audio Analysis (비차단)
→ Preview Export (독립 상태)
→ Result metadata 최종화
```

최종 WAV 생성 성공이 Pipeline 성공 조건이다. Audio Analysis 또는 Preview 실패만으로 재생 가능한 Result를 `FAILED`로 바꾸지 않는다. Pipeline 상태와 별도로 `analysis_status`, `preview.status`를 기록한다. 이 방식은 분석 완료까지 Result 최종화를 기다리는 방식보다 사용자 결과를 보호하고 rollback이 쉽지만, 부분 완료 UX와 후처리 상태 추적이 필요하다.

## K3 단계

### K3.1 Audio Quality Metrics — [계획]

| 분류 | 지표 |
|---|---|
| MVP 필수 | duration, sample rate, channels, sample peak dBFS, clipping 여부·sample count·ratio, Integrated LUFS |
| 조건부 MVP | True Peak dBTP — ITU-R BS.1770 호환 oversampling 구현과 reference 검증을 통과할 때만 |
| 후속 권장 | sample format/bit depth, RMS, Loudness Range, silence ratio, section별 loudness |
| 실험적 | Momentary·Short-term LUFS의 제품 노출 |
| 미지원 | mastering 승인, 음질 점수 자동 확정 |

오버샘플링 없는 최대 sample 값은 `sample_peak_dbfs`다. 이를 True Peak라고 부르지 않는다. True Peak 구현이 확정되기 전 `true_peak_dbtp`는 `null`이며 capability는 planned다. K3 MVP Loudness는 Integrated LUFS에 한정하고 Momentary(400 ms), Short-term(3 s), Loudness Range는 후속으로 둔다. 기준은 ITU-R BS.1770-5와 EBU R 128/Tech 3341이다.

DoD:

- 최종 WAV의 필수 지표를 deterministic하게 계산하고 reference fixture와 비교한다.
- invalid·silence·short·mono/stereo·지원 sample rate 경계를 테스트한다.
- Sample Peak와 True Peak를 명확히 분리하고 미지원 값을 생성하지 않는다.
- 분석 실패가 최종 WAV 재생·다운로드를 막지 않는다.

차단 조건: 표준 구현 미확정, reference 오차 기준 미충족, 내부 경로 공개, Pipeline 성공과 분석 성공의 결합.

### K3.2 Tempo Analysis — [계획]

계약 필드는 `requested_bpm`, `detected_bpm`, `bpm_confidence`, `bpm_error`, `absolute_bpm_error`다. `tempo_stability`와 half/double-time 후보는 후속 권장이다.

```text
bpm_error = detected_bpm - requested_bpm
absolute_bpm_error = abs(detected_bpm - requested_bpm)
```

`detected_bpm`은 정확한 음악적 BPM이 아니라 추정값이다. 하프타임·더블타임 오인, 무박 인트로, 브리지, tempo change와 약한 onset에서는 신뢰도가 낮아질 수 있다.

DoD:

- EVAL-008의 합성·드럼·half/double·무박 인트로·tempo change fixture를 검증한다.
- confidence 산출 근거와 버전을 기록하고 낮은 confidence는 단정적으로 노출하지 않는다.
- 요청값과 분석값을 분리하고 error는 둘 다 있을 때만 계산한다.

차단 조건: ground truth 세트 부재, half/double 오류 미분류, confidence calibration 근거 부재.

### K3.3 Structure·Hook Analysis — [계획]

MVP는 Stage A인 에너지·반복 기반 15초 Hook 후보 1개만 목표로 한다. `first_chorus_time`은 별도 후보이며 확정된 Chorus로 표현하지 않는다.

- Stage A: 단일 Hook 후보, 반복·에너지 근거, confidence
- Stage B: 복수 후보와 calibrated confidence
- Stage C: Lyrics alignment 또는 vocal-aware 분석
- Stage D: 사용자 선택·수정

DoD:

- 후보 구간, confidence, analyzer version을 기록한다.
- 후보가 없으면 정상적인 `not_found` 결과를 제공하고 Pipeline을 실패시키지 않는다.
- EVAL-008의 사용자 label·temporal overlap·Preview 유용성 평가를 통과한다.

차단 조건: “정확한 Hook/Chorus” 표현, ground truth·허용 오차 부재, 저신뢰 후보의 자동 확정.

### K3.4 Preview Export — [계획]

- 기본 형식: 최종 믹스에서 추출한 PCM WAV, MIME `audio/wav`
- 기본 길이: 원본이 15초 이상이면 정확히 15초, 더 짧으면 전체 길이와 `short_source` 표시
- 1순위: Hook 후보 confidence가 provisional `0.50` 이상이고 15초 window가 유효하면 후보 구간
- fallback: 곡 중앙에 정렬한 deterministic 15초 구간
- 경계 처리: 앞·뒤 20 ms linear fade; 원본은 변경하지 않음
- 파일명: 내부 `preview_15s.wav`; 공개 다운로드 filename은 기존 안전한 ASCII 규칙 사용

DoD:

- 길이·RIFF/WAVE·재생·click/fade·원본 비변경을 검증한다.
- Hook 후보와 중앙 fallback을 재현 가능하게 선택한다.
- 기존 secure content/download 검증과 접근 정책을 재사용한다.
- 임시 파일·취소·Result 삭제 cleanup을 검증한다.

차단 조건: 내부 절대 경로 노출, 원본 덮어쓰기, secure access 우회, orphan 파일 cleanup 미정.

## 신뢰도와 사용자 표현

confidence는 `0.0`~`1.0`이며 알고리즘 검증 전 다음 경계는 provisional이다.

| 값 | 등급 | 표현 |
|---:|---|---|
| `0.80` 이상 | high | 높음 |
| `0.50` 이상 `0.80` 미만 | medium | 보통 |
| `0.00` 이상 `0.50` 미만 | low | 낮음·사용자 확인 필요 |
| 값 없음·실패 | unavailable | 분석할 수 없음 |

허용 표현은 “예상 템포”, “Hook 후보”, “Chorus 후보”, “구조 추정”이다. “정확한 BPM”, “확정된 후렴”, “AI가 완벽히 찾음”은 금지한다.

## 성능 예산

60초 Stereo WAV의 K3.1~K3.3 분석은 일반 로컬 CPU에서 수 초~수십 초 이내를 provisional 목표로 둔다. peak memory, CPU time, wall time, 입력 길이, sample rate, cancellation 관찰 지점을 기록한다. 실제 benchmark 전 고정 숫자를 승인 기준으로 사용하지 않으며 긴 곡과 동시 Job 예산은 K3.1 구현 PR에서 확정한다.

