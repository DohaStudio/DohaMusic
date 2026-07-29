# Voice Conversion 모델 조사

> 상태: Phase 4.6 Provider 평가 완료, Primary 미선정
> 기준일: 2026-07-29
> 대상 장비: NVIDIA RTX 3060 Ti 8GB

## 후보 비교

| 후보 | 주 용도 | 한국어 | 노래 입력 | 라이선스·상업 사용 | 8GB 적용성 | 판단 |
|---|---|---|---|---|---|---|
| Seed-VC | zero-shot VC/SVC | 언어 독립 content encoder 경로 | 공식 44.1kHz F0 SVC 모델 | 코드·공식 가중치 GPL-3.0, 배포 전 법무 검토 필요 | 30-step peak 약 5.07GB 실측 | Phase 4 검증 Provider |
| OpenVoice V2 | zero-shot TTS voice cloning | 공식 native 지원 | 공식 문서는 TTS 중심 | MIT, 상업·연구 사용 가능 명시 | 비교적 경량이나 SVC 목적 불일치 | 대안 보류 |
| CosyVoice 3 | multilingual zero-shot TTS | 공식 지원 | TTS 중심 | 코드 Apache-2.0, 가중치별 조건 별도 확인 | LLM 기반으로 통합 복잡도 높음 | 범위 불일치 |
| Fish Speech S2 | multilingual TTS/voice cloning | 다국어 | TTS 중심 | Fish Audio Research License, 상업 사용 별도 계약 | 운영 라이선스 제약 | 제외 |
| RVC | 학습형 VC·AI singer | 모델 언어 품질 확인 필요 | F0·가창 workflow | 코드·공식 배포 모델 MIT 표시, 전체 구성 검토 필요 | 8GB 실측 필요 | Secondary 평가 후보 |
| Amphion Vevo2 | zero-shot VC/SVC | 모델 metadata에 Korean | 공식 style-preserved/converted SVC | 코드 MIT, 가중치 CC BY-NC-ND 4.0 | 8GB 실측 필요 | Experimental |

공식 근거:

- Seed-VC 공식 저장소: https://github.com/Plachtaa/seed-vc
- Seed-VC 공식 모델: https://huggingface.co/Plachta/Seed-VC
- OpenVoice 공식 저장소: https://github.com/myshell-ai/OpenVoice
- CosyVoice 공식 저장소: https://github.com/QwenAudio/CosyVoice
- Fish Speech 공식 저장소: https://github.com/fishaudio/fish-speech
- RVC 공식 저장소: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
- Amphion 공식 저장소: https://github.com/open-mmlab/Amphion
- Vevo2 공식 모델: https://huggingface.co/RMSnow/Vevo2

## 선택

Seed-VC의 `seed-uvit-whisper-base-f0-44k` 계열을 Phase 4 기술 검증 Provider로 선택했다. 소스 보컬의 F0를 유지하도록 설계된 44.1kHz singing voice conversion 모델이며, 훈련 없이 1~30초 참조 음성을 받는 공식 CLI가 이번 입력 계약과 직접 일치한다.

단, 공식 저장소는 2025-11-21부터 archive 상태다. 유지보수와 공급망 위험 때문에 기본 Provider는 `mock`이며, Seed-VC는 고정 커밋 `51383efd921027683c89e5348211d93ff12ac2a8`의 격리형 검증 Provider로만 둔다. 상업 배포 여부는 GPL 의무와 모든 transitive 모델·데이터 라이선스를 별도 검토하기 전 확정하지 않는다.

Phase 4.6에서는 Seed-VC를 포함한 6개 후보를 동일 기준으로 다시 평가했다. 모든 Primary 필수 게이트를 통과한 후보가 없어 표준 Primary는 미선정이며, RVC는 학습형 Secondary 평가 후보, Seed-VC와 Vevo2는 Experimental로 분류했다. 상세 표와 점수는 [Voice Provider 비교](voice-provider-comparison.md)와 [Voice Provider Score](../04-models/voice-provider-score.md)를 따른다.

## 실측 요약

- 공식 예제 source 12.479초, reference 14.597초
- RTX 3060 Ti, CUDA, FP16, F0 condition, diffusion 30 steps
- 3/3 성공, end-to-end 26.17~28.56초
- 시스템 GPU 메모리 peak 5,067~5,069MB
- 출력 12.469초, 48kHz stereo PCM16, 무음 아님
- 3/3에서 peak ≥ 0.999 clipping 경고

이는 공식 예제로 확인한 기술 결과이며 사용자 음성 유사도나 한국어 발음 품질을 의미하지 않는다.
