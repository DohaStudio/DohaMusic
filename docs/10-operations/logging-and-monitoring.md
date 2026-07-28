# 로깅과 모니터링

> 문서 목적: 작업 추적, 성능 관찰과 개인정보 보호 로깅 기준을 정의한다.
> 현재 상태: **설계 초안**

구조화 로그 공통 필드는 timestamp, level, service, request_id, job_id, stage, model_id, event, duration이다. prompt·lyrics·토큰·원본 경로·음성 데이터는 기본 로그에서 제외한다.

메트릭 후보는 상태별 작업 수, 단계별 시간·실패율, 큐 지연, 최대 VRAM, 저장소 오류다. 경보 임계값은 벤치마크 후 정한다. 작업 ID로 API, Worker, 모델 실행 로그를 연결한다.
