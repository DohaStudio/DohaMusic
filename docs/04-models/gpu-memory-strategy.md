# GPU 메모리 전략

> 문서 목적: RTX 3060 Ti 8GB 우선 환경의 측정·실패·완화 원칙을 정의한다.
> 현재 상태: **검증 계획**

- 모델별 로드 직후, 추론 최대, 해제 후 VRAM을 측정한다.
- 전체 파이프라인 모델 동시 적재를 가정하지 않는다.
- OOM은 `GPU_OUT_OF_MEMORY`로 분류하고 입력·모델·설정을 기록한다.
- CPU offload, half precision, 청크 크기는 후보별 품질 회귀와 함께 검증한다.
- 안전한 설정이 확인되기 전 Worker GPU 동시성은 1로 가정한다.

기록 형식은 [GPU 벤치마크 템플릿](../../reports/gpu-benchmark-template.md)을 사용한다.
