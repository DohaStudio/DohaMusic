# EVAL-001: ACE-Step 수동 청취 평가표

> 상태: **[사용자 평가 진행 중]**
> 작성일: 2026-07-29
> 최종 수정일: 2026-07-31
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

모든 경로는 저장소 루트 기준이며 Git에는 포함되지 않는다. EXP-002 기록상 `K-EXP001`과 `K-NOLM-20260729`는 파일 컨테이너 경로만 다르고 PCM 1,920,000 samples가 완전히 동일한 산출물이다. 따라서 `K-EXP001`을 대표 평가로 삼고 `K-NOLM-20260729`는 동일 산출물 참조로만 유지하며 별도 점수 집계에서 제외한다.

현재 8개 ID 중 독립 산출물 5개는 평가를 완료했고, 1개는 그중 하나와 동일한 산출물 참조이며, `B-EXP001`과 `K-NOLM-20260732` 2개는 사용자 평가가 필요하다. 이 때문에 문서 전체 상태는 `[사용자 평가 진행 중]`이다.

| ID | 설정 | 로컬 파일 |
|---|---|---|
| `I-EXP001` | Instrumental, 15초, no LM, Seed 20260729 | `backend/storage/experiments/EXP-001/instrumental/4746130a-598b-ff9c-c851-2acf54984c36.wav` |
| `B-EXP001` | Backend instrumental, 10초, no LM, Seed 20260729 | `backend/storage/experiments/EXP-001/backend-storage/outputs/acb52490-a6e6-455e-9576-d447b3c76321/a0afdd24-0ec3-c936-ab62-951a96699e81.wav` |
| `K-EXP001` | EXP-001 한국어, 20초, no LM, Seed 20260729 | `backend/storage/experiments/EXP-001/korean-lyrics/6e7428e3-021a-fbff-c880-fb38da09ff36.wav` |
| `K-NOLM-20260729` | `K-EXP001`과 동일 PCM 산출물 참조, 별도 점수 집계 제외 | `backend/storage/experiments/EXP-002/resident-memory/same-seed-01/6e7428e3-021a-fbff-c880-fb38da09ff36.wav` |
| `K-NOLM-20260730` | 한국어, 20초, no LM, Seed 20260730 | `backend/storage/experiments/EXP-002/resident-memory/different-seed-01/b613a8ce-b5d7-9425-ced7-d9eb227b213f.wav` |
| `K-NOLM-20260731` | 한국어, 20초, no LM, Seed 20260731 | `backend/storage/experiments/EXP-002/resident-memory/different-seed-02/1caa466a-fab6-4d26-65a5-6ef2048a4511.wav` |
| `K-NOLM-20260732` | 한국어, 20초, no LM, Seed 20260732 | `backend/storage/experiments/EXP-002/resident-memory/different-seed-03/d3eec0ff-57d8-d526-8ced-0c8cb3cf42f3.wav` |
| `K-LM06-20260729` | 한국어, 20초, 0.6B LM, Seed 20260729 | `backend/storage/experiments/EXP-002/lm-0.6b/lm-0.6b-seed-20260729/52cc9201-ee86-ce1a-3e6c-ac3fd7fd14fc.wav` |

## 점수 입력표

빈 점수는 평가하지 않았다는 뜻이다. 점수만 쓰지 말고 문제 구간·가사·판단 근거를 메모한다.

| ID | 음질 | 음악 구조 | 프롬프트 반영 | 한국어 발음 | 가사 일치 | 보컬 자연스러움 | 활용 가능성 | 상태 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `I-EXP001` | 4 | 3 | 4 | 해당 없음 | 해당 없음 | 해당 없음 | 3 | [평가 완료] |
| `B-EXP001` |  |  |  | 해당 없음 | 해당 없음 | 해당 없음 |  | [사용자 평가 필요] |
| `K-EXP001` | 4 | 3 | 3 | 1 | 1 | 1 | 2 | [평가 완료] |
| `K-NOLM-20260729` | — | — | — | — | — | — | — | [동일 산출물 참조] |
| `K-NOLM-20260730` | 4 | 3 | 3 | 1 | 1 | 1 | 2 | [평가 완료] |
| `K-NOLM-20260731` | 4 | 3 | 3 | 1 | 1 | 2 | 2 | [평가 완료] |
| `K-NOLM-20260732` |  |  |  |  |  |  |  | [사용자 평가 필요] |
| `K-LM06-20260729` | 4 | 3 | 4 | 3 | 3 | 3 | 4 | [평가 완료] |

## 항목별 체크

- 음질: [ ] 잡음 [ ] 깨짐 [ ] 금속성 [ ] 클릭 [ ] 클리핑 [ ] 끝부분 절단
- 음악 구조: [ ] 도입 [ ] 전개 [ ] 후렴 [ ] 자연스러운 종료
- 프롬프트: [ ] 한국어 팝 발라드 [ ] 피아노 [ ] 스트링 [ ] 여성 솔로 [ ] 따뜻하고 쓸쓸한 분위기
- 발음: [ ] 자음 [ ] 모음 [ ] 받침 [ ] 운율 [ ] 외국어 억양
- 가사: [ ] 누락 [ ] 치환 [ ] 반복 [ ] 순서 변경 [ ] 시간 정렬
- 보컬: [ ] 음정 [ ] 호흡 [ ] 비브라토 [ ] 보컬/반주 균형

## 사용자 메모

### `I-EXP001`

- 점수 근거: 피아노 중심의 잔잔한 분위기가 잘 표현됐고 심한 잡음, 깨짐, 클리핑은 확인되지 않았다. 피아노 발라드용 반주 소재로 활용 가능하다.
- 문제 구간: 15초 생성이라 완성곡보다 도입부 또는 짧은 배경음악에 가깝고, 음악적 전개와 자연스러운 종료가 부족하다.

### `B-EXP001`

- 점수 근거: [사용자 평가 필요]
- 문제 구간: [사용자 평가 필요]

### `K-EXP001`

- 발음·가사: 명확한 한국어 가창이 거의 들리지 않고 입력 가사를 식별할 수 없어 가사 재현 결과로는 실패에 가깝다.
- 음악·보컬: 피아노와 스트링 기반 발라드 분위기는 생성됐으나 가창 생성에는 부적합하다. 반주 결과로는 일부 활용 가능하다.
- 문제 구간: 한국어 발음·가사 일치·보컬 자연스러움 전반.

### `K-NOLM-20260729`

- 판정: EXP-002의 PCM 비교 결과에 따라 `K-EXP001`과 동일 산출물로 확인했다. 독립 사용자 평가나 별도 점수 집계에 포함하지 않는다.
- 청취 근거: `K-EXP001` 대표 평가를 참조한다.

### Seed 다양성 비교

- 20260729: 반주는 생성됐으나 한국어 가창이 사실상 누락됐다.
- 20260730: Seed 변경으로 멜로디와 편곡은 달라졌지만 한국어 가사 누락 문제는 동일했다.
- 20260731: 여성 보컬 형태의 길게 이어지는 발성은 생성됐으나 실제 가사 대신 모음 중심의 보컬라이즈에 가까웠다. 보컬 음색 생성 가능성은 확인했지만 입력 가사 제어에 실패했고 후속 음색 변환 입력으로 사용하기에는 불안정하다.
- 20260732: [사용자 평가 필요]
- 프롬프트 일관성: 피아노와 스트링 중심의 잔잔한 발라드 스타일은 비교적 일관됐다. 그러나 no LM에서는 Seed에 따라 보컬 존재 여부와 형태가 크게 달랐고, 한국어 가사 재현성과 보컬 안정성은 낮았다.

### no LM 대 0.6B LM

- 더 나은 출력과 이유: `K-LM06-20260729`. 평가한 결과 중 유일하게 한국어 문장 형태의 가창이 명확히 생성됐고 여성 솔로와 잔잔한 피아노 발라드 프롬프트가 비교적 명확히 반영됐다.
- 가사·발음 차이: no LM은 가사가 누락되거나 모음 발성만 생성됐다. 0.6B LM은 일부 자음과 받침이 뭉개지고 음절 길이가 부자연스럽지만 한국어 문장과 주요 단어를 식별할 수 있어 가사 전달력과 보컬 생성 품질이 크게 개선됐다.
- 프롬프트·구조 차이: 두 설정 모두 피아노 발라드 분위기를 일부 반영했고, 0.6B LM에서 보컬 생성과 가사 제어가 뚜렷하게 개선됐다. 20초 결과이므로 전체 곡 구조와 후렴 품질은 아직 검증되지 않았다.
- 활용 판단: 한국어 가창에는 no LM을 기본 설정으로 사용하지 않는다. 0.6B LM은 실험 기본 설정 후보이며 후속 음색 변환 입력으로 추가 검증할 가치가 있다.

## 평가 완료 조건

모든 대상의 적용 가능한 항목에 점수와 근거가 있고, no LM/0.6B LM 선호 및 후속 음색 변환 활용 가능성 의견이 기록되면 사용자 평가를 완료로 바꾼다.

## 향후 대표 평가 시나리오

기존 점수표는 당시 실행한 Instrumental과 Korean Ballad 결과의 근거로 유지한다. 이후 비교는 다음 세 축으로 구성하며 **Korean Dance Pop을 제품 대표 시나리오**로 사용한다.

1. Instrumental — 짧은 반주 생성과 기본 음질을 확인하는 보조 시나리오
2. Korean Ballad — 기존 한국어 가창 결과와 비교하기 위한 보조 시나리오
3. Korean Dance Pop (Primary) — 한국 여성 댄스팝 생성과 후속 Voice Conversion 입력 적합성을 판단하는 대표 시나리오

## Korean Dance Pop 평가 기준

기존 음질·음악 구조·프롬프트 반영·한국어 발음·가사 일치·보컬 자연스러움·활용 가능성 기준은 유지하고 다음 항목을 대표 시나리오에 추가한다.

| 평가 항목 | 확인 기준 |
|---|---|
| 리듬감 | 일정한 박과 싱코페이션이 곡 전체에서 자연스럽게 유지되는가 |
| Kick | 전자 Kick의 타격감이 분명하고 Bass·보컬을 과도하게 가리지 않는가 |
| Bass | 저역이 깊고 안정적이며 Kick과 함께 Dance Groove를 형성하는가 |
| Dance Groove | 몸을 움직일 수 있는 반복적 추진력과 박자 흐름이 있는가 |
| Energy | Verse에서 Chorus로 갈수록 에너지가 설득력 있게 상승하는가 |
| Verse | 가사 전달과 리듬을 확보하면서 다음 섹션을 준비하는가 |
| Pre-Chorus | 긴장과 상승감을 만들고 Chorus 진입을 명확히 예고하는가 |
| Chorus | Verse와 구분되는 크기·밀도·멜로디로 핵심 절정을 형성하는가 |
| Hook | 짧고 반복 가능하며 한 번 청취한 뒤 기억할 수 있는 핵심 구절인가 |
| 보컬 선명도 | 여성 Lead Vocal이 반주에 묻히지 않고 음절과 멜로디를 식별할 수 있는가 |
| 한국어 발음 | 자음·모음·받침과 음절 길이가 자연스럽고 주요 단어를 알아들을 수 있는가 |
| 춤 가능성 | 120~128 BPM 범위에서 박자·Groove·Energy가 실제 Dance 동작을 지지하는가 |

## Korean Dance Pop 대표 Prompt 예시

다음 Prompt는 향후 실험 입력 예시이며 아직 실행 결과가 아니다.

```text
Energetic modern Korean dance-pop.
Female lead vocal.
124 BPM.
Punchy electronic kick.
Deep bass.
Bright synths.
Commercial K-pop production.
Clear Korean pronunciation.
Verse → Pre-Chorus → Chorus.
Catchy explosive chorus.
Danceable groove.
Radio-ready mix.
```

## Hook 중심 Lyrics 예시

다음 가사는 구조·발음·Hook 평가를 위한 짧은 자체 작성 예시다.

```text
[Verse]
네온빛이 번진 이 거리 위로
한 걸음 더 가까이 뛰어

[Pre-Chorus]
심장이 더 빠르게 울려
지금 이 순간을 깨워

[Chorus]
Turn it up, turn it up
우리의 밤을 밝혀
Turn it up, turn it up
멈추지 마 더 높이
```

## Dance Pop Evaluation Plan

- 모델 구성: Base Model과 0.6B LM을 우선 평가하며 no LM은 한국어 가창 대표 설정으로 사용하지 않는다.
- Tempo: 120~128 BPM, 기준 Prompt는 124 BPM으로 고정한다.
- 생성 길이: Verse → Pre-Chorus → Chorus 판정이 가능한 60~90초를 목표로 한다.
- Seed: 같은 Prompt·Lyrics·모델 설정에서 3개 이상 Seed를 비교한다.
- 평가: 기존 공통 항목과 Korean Dance Pop 추가 항목을 함께 기록하고, 후속 Voice Conversion 입력으로 보컬이 충분히 선명하고 안정적인지 확인한다.
- 상태: 계획이며 모델 실행, 새 점수 작성, 운영 Provider 승인을 의미하지 않는다.

## LoRA와 향후 데이터 방향

현재 Phase 2에서는 ACE-Step Base Model 평가가 목적이다. Dance 스타일 LoRA는 현재 적용 대상이 아니며 Phase 7 이후 검토 대상으로 유지한다.

향후 Style Fine-tuning을 검토할 때는 Korean Dance Pop, Synth Pop, Electro Pop, House 기반 Pop을 우선 후보로 둔다. 직접 제작했거나 학습·파생 모델·상업 이용 권리를 확인한 데이터만 사용하며, 상업 음원을 무단 수집하거나 학습하지 않는다.
