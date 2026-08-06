# 문제 해결

> 문서 목적: 향후 자주 발생할 로컬·파이프라인 문제의 진단 순서를 정의한다.
> 현재 상태: **초안**

## GPU OOM

모델·버전, 입력 길이, precision, offload, 단계 시작/최대 VRAM을 확인한다. 자동 재시도 전에 [GPU 메모리 전략](../04-models/gpu-memory-strategy.md)의 승인 설정인지 확인한다.

## 작업 정지

lease/heartbeat, Worker 생존, 현재 단계, 저장소·DB 연결을 확인한다. 동일 작업을 수동 중복 실행하지 말고 재시도 API를 사용한다.

`CANCEL_REQUESTED`가 오래 유지되면 현재 Provider 단계 종료 여부와 Worker 로그를 확인한다. 로컬 MVP는 subprocess를 무조건 kill하지 않으며 단계 경계에서 취소를 확정한다. `CANCELLED`인데 공개 final 파일이 보이면 파일 제공을 중단하고 DB·Storage 정합성을 점검한다. Retry가 `RETRY_VOICE_PROFILE_UNAVAILABLE`이면 원본 Voice Profile의 존재·`READY` 상태·동의를 확인하고 새 목소리로 새 음악을 만든다.

## ACE-Step 상주 메모리 증가

현재 운영 방식은 Job별 subprocess다. benchmark에서 상주 6회 동안 process RSS가 약 14.2GiB 증가했으므로 임의로 상주 Worker로 바꾸지 않는다. 실험 시 run 직전·peak·직후의 process RSS, 시스템 메모리, Torch allocated/reserved를 함께 기록하고 프로세스 종료 후 회수를 확인한다. 시스템 메모리가 부족하면 새 요청을 중단하고 다른 사용자 프로세스를 강제로 종료하지 않는다.

## 0.6B LM

RTX 3060 Ti 8GB 검증은 공식 0.6B 모델, PyTorch backend, CPU offload 조합이다. checkpoint가 없으면 자동 다운로드하지 않고 `AI_MODEL_NOT_FOUND`로 중단한다. LM이 실행돼도 청취 평가 전에는 no-LM보다 품질이 좋다고 판단하지 않는다.

## 오디오 오류

실제 디코딩, 형식·크기·길이, 저장소 해시, 단계별 출력 검증을 확인한다. 같은 Seed 재현성은 WAV 파일 hash뿐 아니라 sample hash·RMSE도 확인한다. ACE-Step WAV는 IEEE float32일 수 있어 PCM16 전용 reader로 실패할 수 있다. 원본을 덮어쓰지 않는다.

## Demucs Stem 실패

`DOHAMUSIC_STEM_PROVIDER=demucs`, 격리 Python·runner·model cache 경로, cache 안의 `.safetensors`, CUDA 인식 순으로 확인한다. 실행기는 오프라인이므로 누락 모델을 내려받지 않고 `STEM_MODEL_NOT_FOUND`로 중단한다. OOM이면 다른 프로세스를 강제 종료하지 말고 GPU 동시성 1, segment 7초 설정과 시스템 GPU 사용량을 확인한다.

결과가 생성됐지만 품질이 낮다고 느껴지면 파일 존재·48kHz·Stereo·동일 길이·RMS·clipping을 먼저 확인한 뒤 EVAL-002에 보컬 누락·누출·잔향·노이즈 구간을 기록한다. 자동 지표만으로 모델을 교체하거나 Seed-VC에 연결하지 않는다.
