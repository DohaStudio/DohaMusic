# 문제 해결

> 문서 목적: 향후 자주 발생할 로컬·파이프라인 문제의 진단 순서를 정의한다.
> 현재 상태: **초안**

## GPU OOM

모델·버전, 입력 길이, precision, offload, 단계 시작/최대 VRAM을 확인한다. 자동 재시도 전에 [GPU 메모리 전략](../04-models/gpu-memory-strategy.md)의 승인 설정인지 확인한다.

## 작업 정지

lease/heartbeat, Worker 생존, 현재 단계, 저장소·DB 연결을 확인한다. 동일 작업을 수동 중복 실행하지 말고 재시도 API를 사용한다.

## ACE-Step 상주 메모리 증가

현재 운영 방식은 Job별 subprocess다. benchmark에서 상주 6회 동안 process RSS가 약 14.2GiB 증가했으므로 임의로 상주 Worker로 바꾸지 않는다. 실험 시 run 직전·peak·직후의 process RSS, 시스템 메모리, Torch allocated/reserved를 함께 기록하고 프로세스 종료 후 회수를 확인한다. 시스템 메모리가 부족하면 새 요청을 중단하고 다른 사용자 프로세스를 강제로 종료하지 않는다.

## 0.6B LM

RTX 3060 Ti 8GB 검증은 공식 0.6B 모델, PyTorch backend, CPU offload 조합이다. checkpoint가 없으면 자동 다운로드하지 않고 `AI_MODEL_NOT_FOUND`로 중단한다. LM이 실행돼도 청취 평가 전에는 no-LM보다 품질이 좋다고 판단하지 않는다.

## 오디오 오류

실제 디코딩, 형식·크기·길이, 저장소 해시, 단계별 출력 검증을 확인한다. 같은 Seed 재현성은 WAV 파일 hash뿐 아니라 sample hash·RMSE도 확인한다. ACE-Step WAV는 IEEE float32일 수 있어 PCM16 전용 reader로 실패할 수 있다. 원본을 덮어쓰지 않는다.
