# 음악 생성 어댑터

> 문서 목적: 교체 가능한 음악 생성 Provider의 계약을 정의한다.
> 현재 상태: **Mock·ACE-Step Adapter 구현**

공통 입력은 Job ID, prompt, 선택적 lyrics·genre·duration·seed다. 공통 결과는 WAV 경로, Provider, 모델명·버전, 실제 Seed, 실제 길이, 추론 시간, 최대 VRAM, 메타데이터 경로다. Worker와 서비스는 ACE-Step 타입을 import하지 않는다.

`AceStepAdapter`는 입력을 공식 실행기의 `GenerationParams`/`GenerationConfig` 계약으로 변환하고, 격리 subprocess를 호출해 결과 JSON을 공통 결과로 되돌린다. prompt나 lyrics가 없는 instrumental 요청은 `instrumental=true`로 매핑한다. 현재 출력은 WAV만 지원한다.

| 오류 | 조건 |
|---|---|
| `AI_DEPENDENCY_NOT_INSTALLED` | 격리 Python·runner가 없음 |
| `AI_MODEL_NOT_FOUND` | 프로젝트·checkpoint·모델 경로가 없음 |
| `AI_MODEL_LOAD_FAILED` | 모델 초기화 실패 |
| `AI_INFERENCE_FAILED` | 추론 또는 잘못된 runner 응답 |
| `AI_OUT_OF_MEMORY` | CUDA 메모리 부족 |
| `AI_OUTPUT_NOT_CREATED` | 성공 응답이나 WAV가 없음 |
| `AI_AUDIO_DECODE_FAILED` | 생성 파일의 WAV metadata 해석 실패 |
| `AI_TIMEOUT` | 설정된 실행 제한 초과 |

모델 다운로드는 Adapter 책임이 아니다. ACE-Step을 선택해도 애플리케이션 import·시작 시 모델을 로드하지 않으며, 실제 Job 실행 때 설치 검증 후 subprocess가 로드한다.
