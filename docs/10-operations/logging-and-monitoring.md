# 로깅과 모니터링

> 문서 목적: 작업 추적·성능 측정과 입력 보호 기준을 정의한다.
> 현재 상태: **Backend·ACE-Step 실험 로그 구현**

Backend는 요청, Job 생성, Worker·추론 시작/종료, Provider·모델·버전, 처리 시간, 최대 VRAM과 예외 코드를 기록한다. ACE-Step 실행기는 모델 로드·추론·전체 시간, Torch allocated/reserved, `nvidia-smi` 전체 사용량, process RSS, 장치·양자화·offload, 실제 Seed와 WAV 정보를 metadata JSON에 기록한다.

prompt·lyrics·비밀 값과 로컬 절대 경로는 Backend 로그에 기록하지 않는다. 공식 ACE-Step 라이브러리가 `conditioning_text`를 INFO로 출력하는 동작을 확인해 실행기에서 해당 record를 필터링했다. 로그를 외부로 전송할 때는 재차 민감 정보 검사를 수행한다.

`nvidia-smi` 수치는 같은 GPU의 시스템 전체 값이다. 다중 샘플 평균, 외부 메트릭 저장, 경보와 상주 Worker 누수 모니터링은 아직 구현하지 않았다.
