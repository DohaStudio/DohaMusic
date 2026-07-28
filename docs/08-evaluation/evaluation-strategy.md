# 평가 전략

> 문서 목적: 모델과 파이프라인을 재현 가능하게 평가한다.
> 현재 상태: **ACE-Step·HTDemucs 기술 베이스라인 확보 / 사용자 청취 평가 대기**

평가는 실행 가능성, 성능, 객관적 신호, 주관적 청취를 분리한다. 고정 JSON 입력에 모델 버전, Seed, 길이, 장치·양자화·offload 설정을 기록한다. EXP-002는 같은 Seed 3회, 다른 Seed 3회와 상주 6회 suite 2개를 사용했다. 표본이 작고 단일 PC 결과이므로 다른 환경으로 일반화하지 않는다.

객관적 항목은 파일 존재, WAV 구조, 샘플레이트·채널·길이·크기, peak·RMS·near-silence·clip 비율과 sample hash·RMSE·상관계수다. 파일 hash와 sample hash를 구분한다. EXP-002 동일 Seed 출력은 컨테이너 hash가 달라도 PCM이 완전히 같았고, 다른 Seed 출력은 서로 다른 파형이었다.

EXP-003 Stem 평가는 같은 20초 입력을 HTDemucs로 3회 분리하고 성공률, 모델 load·분리·전체 시간, Torch 및 시스템 GPU memory, process RSS, CPU와 두 출력의 객관 지표를 기록했다. 3/3 성공했지만 단일 입력·단일 PC 결과다.

다음 항목은 사람이 출력 파일을 직접 듣고 1~5점과 근거를 기록해야 한다.

- 한국어 자음·모음·받침과 자연스러운 운율
- 입력 가사 누락·치환·반복 및 시간 정렬
- 보컬 존재 여부와 보컬/반주 균형
- 곡 구조, 장르·분위기 일치와 음악성
- 클릭·왜곡·금속성 잡음·끝부분 절단

현재 위 청취 항목은 모두 `[사용자 평가 필요]`다. [EVAL-001](../../reports/evaluations/EVAL-001-ace-step-listening-evaluation.md)에 사용자가 직접 점수와 근거를 기록하기 전에는 ACE-Step을 제품 기본 모델로 승인하지 않는다.

Stem 분리의 보컬 누락·누출·반주 손상·잔향·노이즈·Seed-VC 활용 가능성은 [EVAL-002](../../reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md)에 사용자가 기록한다. 자동 신호 지표만으로 HTDemucs 청감 품질을 승인하지 않는다.
