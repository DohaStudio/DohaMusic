# EVAL-008: Audio Analysis 검증 계획

> 상태: [계획]
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: K3.1~K3.4 Audio Quality·Tempo·Hook·Preview 평가
> 관련 문서: [K3 제품 정의](../../docs/02-product/k3-audio-analysis-product-definition.md), [라이브러리 비교](../../docs/01-research/audio-analysis-library-comparison.md), [EVAL-007](EVAL-007-kpop-dance-generation.md)

## 목적과 원칙

K3 analyzer가 측정값·추정값·실패를 계약대로 구분하는지 검증한다. 이번 문서는 평가 설계이며 실측·청취 결과를 기록하지 않는다. 생성 음원과 개인 음성은 Git에 커밋하지 않는다.

## 공통 기록

- fixture ID·권리·hash, WAV format·sample rate·channels·duration
- `audio_analysis_version`과 각 후보 library/version/config
- CPU·OS·Python, wall/CPU time, peak RSS
- ground truth/reference tool과 허용 오차
- status·warning·confidence, 실패 원인
- 실제 값, absolute/relative error, 통과 여부

## BPM 검증

| 데이터 | 목적 |
|---|---|
| 메트로놈 합성 60·90·120·124·150 BPM | 명확한 ground truth |
| 고정 BPM drum loop | 실제 transient 패턴 |
| half-time·double-time 편곡 | octave tempo 오류 분류 |
| 무박 intro 후 고정 tempo | 초기 무박 영향 |
| tempo change 곡 | global tempo 한계·stability |
| 30초·60초 권리 확보 K-POP Dance 결과 | 제품 대표성, 자동 ground truth 아님 |

측정값은 detected BPM, ground truth BPM, signed/absolute error, confidence, half/double error, 분석 시간을 포함한다. provisional 자동 통과 기준은 명확한 합성/고정 loop에서 half/double 보정 후 absolute error 2 BPM 이내다. 생성곡은 수동 beat annotation과 비교하며 기준은 구현 benchmark 후 확정한다.

confidence는 high/medium/low/unavailable 구간별 실제 오류 분포를 검토한다. 높은 confidence가 더 낮은 오류와 연결되지 않으면 UI 등급으로 사용하지 않는다.

## Loudness·Peak 검증

- Sample Peak: synthetic impulse·sine의 계산값과 reference 비교
- Integrated LUFS: ITU-R BS.1770/EBU R 128 test signal 및 승인 reference meter 비교
- True Peak: 표준 test signal과 reference meter 비교; oversampling 미구현이면 미지원 유지
- Clipping: positive/negative full-scale, over-range float, clipped PCM
- Mono·Stereo와 44.1/48 kHz
- short audio, silence, empty/invalid/truncated WAV

LUFS·True Peak 허용 오차는 사용 library와 EBU test set의 compliance 조건을 확인한 뒤 확정한다. reference 후보는 EBU Loudness test set과 라이선스 검토된 FFmpeg/전용 meter다. 단순 RMS 또는 Sample Peak를 LUFS·True Peak reference로 사용하지 않는다.

## Hook·Chorus 후보 검증

권리 확보 또는 합성 데이터에 사용자가 반복 구간과 Chorus 시작 후보를 annotation한다.

- 허용 start/end 오차
- 후보와 label의 temporal overlap·IoU
- top-1 precision, candidate recall
- 반복 score·energy contrast와 confidence calibration
- 15초 Preview 후보로 사용 가능한지
- 사용자가 곡의 핵심 구간으로 느끼는지
- 반복 청취에 적합한지

Hook ground truth는 본질적으로 주관적이므로 “정확도” 단일 숫자로 승인하지 않는다. Stage A의 제품 Gate는 top-1 후보의 Preview 유용성과 저신뢰 결과의 안전한 fallback이다.

## Preview 검증

- 원본이 15초 이상이면 frame 기준 정확히 15초
- short source 정책과 중앙 fallback 재현성
- RIFF/WAVE 재생 가능, channel·sample rate 유지
- 원본 파일 hash 불변
- 20 ms fade in/out과 시작·끝 click 청취
- Hook 후보 대표성, fallback 정상 동작
- secure content/download, Range, MIME, path 비노출
- 취소·실패·Job/Result 삭제 cleanup과 orphan 부재

## 실패·호환 검증

- 분석 없음 구형 Result는 정상 재생되고 `not_requested/unavailable`로 표시된다.
- 일부 analyzer 실패는 `partial`, 전체 분석 실패는 `failed/unsupported`가 되며 Pipeline Result는 유지된다.
- malformed metadata·unknown version·내부 경로는 공개 DTO에서 제거된다.
- Retry는 새 WAV를 분석하고 기존 결과를 복사하지 않는다.
- Re-analysis가 도입되면 동일 WAV·새 version 관계와 기존 결과 보존을 검증한다.

## 성능·취소 검증

60초 Stereo WAV 기준 wall/CPU time, peak RSS, file size와 cancellation latency를 측정한다. “일반 CPU에서 수 초~수십 초”는 provisional 예산이며 실제 장비·동시 Job·긴 곡 결과로 K3.1 구현 PR에서 상한을 확정한다. 측정하지 않은 수치를 완료 근거로 사용하지 않는다.

## 완료 판정

- [ ] K3.1 quality reference와 invalid 경계 통과
- [ ] K3.2 BPM error·half/double·confidence calibration 통과
- [ ] K3.3 Hook 후보 overlap·사용자 유용성 평가 통과
- [ ] K3.4 정확한 길이·fade·secure access·cleanup 통과
- [ ] 성능·취소 예산 기록
- [ ] 실패·partial·unsupported와 구형 Result 회귀 통과

현재 결과: `[미실행]`
