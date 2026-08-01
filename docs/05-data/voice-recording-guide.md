# 음성 녹음 가이드

> 문서 상태: [계획] [검증 필요]
> 최종 수정일: 2026-08-01
> 문서 목적: 권리와 품질 기준을 만족하는 참조 음성 수집 방법을 안내한다.
> 관련 문서: [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md), [음성 동의 정책](../09-security/voice-consent-policy.md), [데이터 품질 체크리스트](data-quality-checklist.md)

- 본인 음성 또는 명시적 동의를 받은 음성만 녹음한다.
- 조용한 환경, 일정한 마이크 거리, 무반주·무효과 원본을 권장한다.
- 클리핑, 긴 무음, 배경 음악, 여러 화자가 섞인 파일을 피한다.
- 현재 Voice Profile upload는 한 개의 25MB 이하, 5~60초, 16-bit PCM, 16kHz 이상 mono/stereo WAV만 허용한다.
- MediaRecorder WebM/Ogg, MP3·M4A와 다중 sample은 현재 지원하지 않는다. Guided Enrollment의 정규화·sample 모델은 `[ADR 필요] [Backend 확장 필요]`다.
- 업로드 전 음성 사용 목적, 보존, 철회·삭제 방법을 확인한다.

안내 문장, 음역·가창 sample, 길이 정책, 브라우저 녹음과 품질 검사는 [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md)을 따른다. 모델별 총 길이·sample 수·말하기/노래 비율은 검증 전 확정하지 않는다. Phase 7 개인화 Dataset 수집은 단일 참조 음성 등록과 별도 목적·동의·lineage를 사용한다.
