# EVAL-001: ACE-Step 수동 청취 평가표

> 상태: **[사용자 평가 필요]**
> 작성일: 2026-07-29
> 관련 실험: [EXP-001](../experiments/EXP-001-ace-step-local-inference.md), [EXP-002](../experiments/EXP-002-ace-step-quality-and-stability.md)

## 평가 방법

로컬 ignored 경로의 WAV를 헤드폰 또는 기준 스피커로 듣고 각 항목에 1~5점과 근거를 기록한다. 기계 검증 통과나 파형 차이를 청감 품질 합격으로 해석하지 않는다.

| 점수 | 기준 |
|---:|---|
| 1 | 사용할 수 없음 |
| 2 | 문제가 많음 |
| 3 | 일부 활용 가능 |
| 4 | 양호 |
| 5 | 매우 양호 |

## 평가 대상

모든 경로는 저장소 루트 기준이며 Git에는 포함되지 않는다. 동일 Seed 반복본은 PCM 샘플이 완전히 같으므로 `K-NOLM-20260729` 한 개를 대표 청취한다.

| ID | 설정 | 로컬 파일 |
|---|---|---|
| `I-EXP001` | Instrumental, 15초, no LM, Seed 20260729 | `backend/storage/experiments/EXP-001/instrumental/4746130a-598b-ff9c-c851-2acf54984c36.wav` |
| `B-EXP001` | Backend instrumental, 10초, no LM, Seed 20260729 | `backend/storage/experiments/EXP-001/backend-storage/outputs/acb52490-a6e6-455e-9576-d447b3c76321/a0afdd24-0ec3-c936-ab62-951a96699e81.wav` |
| `K-EXP001` | EXP-001 한국어, 20초, no LM, Seed 20260729 | `backend/storage/experiments/EXP-001/korean-lyrics/6e7428e3-021a-fbff-c880-fb38da09ff36.wav` |
| `K-NOLM-20260729` | 한국어, 20초, no LM, Seed 20260729 | `backend/storage/experiments/EXP-002/resident-memory/same-seed-01/6e7428e3-021a-fbff-c880-fb38da09ff36.wav` |
| `K-NOLM-20260730` | 한국어, 20초, no LM, Seed 20260730 | `backend/storage/experiments/EXP-002/resident-memory/different-seed-01/b613a8ce-b5d7-9425-ced7-d9eb227b213f.wav` |
| `K-NOLM-20260731` | 한국어, 20초, no LM, Seed 20260731 | `backend/storage/experiments/EXP-002/resident-memory/different-seed-02/1caa466a-fab6-4d26-65a5-6ef2048a4511.wav` |
| `K-NOLM-20260732` | 한국어, 20초, no LM, Seed 20260732 | `backend/storage/experiments/EXP-002/resident-memory/different-seed-03/d3eec0ff-57d8-d526-8ced-0c8cb3cf42f3.wav` |
| `K-LM06-20260729` | 한국어, 20초, 0.6B LM, Seed 20260729 | `backend/storage/experiments/EXP-002/lm-0.6b/lm-0.6b-seed-20260729/52cc9201-ee86-ce1a-3e6c-ac3fd7fd14fc.wav` |

## 점수 입력표

빈 점수는 평가하지 않았다는 뜻이다. 점수만 쓰지 말고 문제 구간·가사·판단 근거를 메모한다.

| ID | 음질 | 음악 구조 | 프롬프트 반영 | 한국어 발음 | 가사 일치 | 보컬 자연스러움 | 활용 가능성 | 상태 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `I-EXP001` |  |  |  | 해당 없음 | 해당 없음 | 해당 없음 |  | [사용자 평가 필요] |
| `B-EXP001` |  |  |  | 해당 없음 | 해당 없음 | 해당 없음 |  | [사용자 평가 필요] |
| `K-EXP001` |  |  |  |  |  |  |  | [사용자 평가 필요] |
| `K-NOLM-20260729` |  |  |  |  |  |  |  | [사용자 평가 필요] |
| `K-NOLM-20260730` |  |  |  |  |  |  |  | [사용자 평가 필요] |
| `K-NOLM-20260731` |  |  |  |  |  |  |  | [사용자 평가 필요] |
| `K-NOLM-20260732` |  |  |  |  |  |  |  | [사용자 평가 필요] |
| `K-LM06-20260729` |  |  |  |  |  |  |  | [사용자 평가 필요] |

## 항목별 체크

- 음질: [ ] 잡음 [ ] 깨짐 [ ] 금속성 [ ] 클릭 [ ] 클리핑 [ ] 끝부분 절단
- 음악 구조: [ ] 도입 [ ] 전개 [ ] 후렴 [ ] 자연스러운 종료
- 프롬프트: [ ] 한국어 팝 발라드 [ ] 피아노 [ ] 스트링 [ ] 여성 솔로 [ ] 따뜻하고 쓸쓸한 분위기
- 발음: [ ] 자음 [ ] 모음 [ ] 받침 [ ] 운율 [ ] 외국어 억양
- 가사: [ ] 누락 [ ] 치환 [ ] 반복 [ ] 순서 변경 [ ] 시간 정렬
- 보컬: [ ] 음정 [ ] 호흡 [ ] 비브라토 [ ] 보컬/반주 균형

## 사용자 메모

### `I-EXP001`

- 점수 근거:
- 문제 구간:

### `B-EXP001`

- 점수 근거:
- 문제 구간:

### `K-EXP001`

- 발음·가사:
- 음악·보컬:
- 문제 구간:

### `K-NOLM-20260729`

- 발음·가사:
- 음악·보컬:
- 문제 구간:

### Seed 다양성 비교

- 20260730:
- 20260731:
- 20260732:
- 프롬프트 일관성:

### no LM 대 0.6B LM

- 더 나은 출력과 이유:
- 가사·발음 차이:
- 프롬프트·구조 차이:

## 평가 완료 조건

모든 대상의 적용 가능한 항목에 점수와 근거가 있고, no LM/0.6B LM 선호 및 후속 음색 변환 활용 가능성 의견이 기록되면 사용자 평가를 완료로 바꾼다.
