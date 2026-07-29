# Voice Provider 비교

> 문서 상태: [완료]
> 기준일: 2026-07-29
> 범위: 공식 저장소·공식 모델 카드·기존 EXP-004 기반 문서 평가

## 조사 원칙

- GitHub Stars와 최근 push는 2026-07-29 GitHub API 응답을 고정한 값이다. Stars는 품질이 아니라 Community 규모 참고치다.
- 활성 개발은 `archive가 아니고 최근 180일 내 push`인 경우로 표시했다. 1년 넘게 push가 없으면 저활동, archive이면 중단으로 분류했다.
- VRAM은 공식 수치나 DohaMusic 실측만 기록한다. 모델 크기로 VRAM을 추정하지 않는다.
- 한국어 문서가 있다는 사실과 한국어 모델 지원은 구분한다.
- TTS voice cloning과 singing voice conversion은 동일 기능으로 간주하지 않는다.

## 비교표

| Provider | 공식 저장소 | Stars | 최근 push | Archive·유지보수 | License | 한국어 | Singing VC | GPU·VRAM | Speed | Backend 적용 | 상업 사용 |
|---|---|---:|---|---|---|---|---|---|---|---|---|
| Seed-VC | [Plachtaa/seed-vc](https://github.com/Plachtaa/seed-vc) | 3,891 | 2025-04-20 | Archive / 중단 | 코드·공식 모델 GPL-3.0 | 공식 명시 없음 | 공식 zero-shot SVC | RTX 3060 Ti 5,067~5,069MB 실측 | 12.469초 출력 평균 27.224초 | 현재 계약과 일치, Adapter 구현됨 | 가능하나 배포 시 GPL 검토 필요 |
| OpenVoice V2 | [myshell-ai/OpenVoice](https://github.com/myshell-ai/OpenVoice) | 37,040 | 2025-04-19 | 비archive / 저활동 | V1·V2 MIT | 공식 native Korean | 공식 문서는 speech/TTS tone-color cloning 중심 | GPU·8GB VRAM 검증 필요 | 동등 조건 검증 필요 | zero-shot tone converter는 유사하나 singing 미확인 | MIT 고지 조건으로 가능, 구성요소 재검토 |
| CosyVoice | [QwenAudio/CosyVoice](https://github.com/QwenAudio/CosyVoice) | 22,464 | 2026-05-25 | 활성 | 코드·CosyVoice2 모델 Apache-2.0 | 공식 지원 | 공식 주 목적은 multilingual TTS, singing 미확인 | GPU·8GB VRAM 검증 필요 | 공식 150ms streaming 주장은 TTS라 직접 비교 불가 | text→speech 중심, 현재 source vocals 계약과 불일치 | Apache-2.0 고지·NOTICE 검토 후 가능 |
| Fish Speech | [fishaudio/fish-speech](https://github.com/fishaudio/fish-speech) | 31,423 | 2026-07-26 | 활성 | Fish Audio Research License | 공식 모델에서 Korean 지원 | 공식 주 목적은 TTS, singing 미확인 | GPU·8GB VRAM 검증 필요 | 동등 조건 검증 필요 | text→speech 중심, 현재 계약과 불일치 | 별도 서면 상업 라이선스 필요 |
| RVC | [RVC-Project/Retrieval-based-Voice-Conversion-WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) | 36,787 | 2026-07-23 | 활성 | 코드 MIT, 공식 배포 모델 카드 MIT; 구성요소별 재검토 | 한국어 UI 문서는 있으나 모델 지원 근거 아님 | AI singer·F0 workflow 제공, 사용자별 학습 필요 | GPU 지원, 8GB VRAM 실측 필요 | 공식 realtime 지연 수치는 장치 의존, offline 비교 불가 | 학습된 checkpoint·index가 필요해 zero-shot 계약과 불일치 | core는 가능, 학습 데이터·모델·의존성 권리 검토 필요 |
| Amphion Vevo2 | [open-mmlab/Amphion](https://github.com/open-mmlab/Amphion) | 9,972 | 2026-03-25 | 활성 | 코드 MIT, [Vevo2 가중치](https://huggingface.co/RMSnow/Vevo2) CC BY-NC-ND 4.0 | 모델 카드 metadata에 Korean | 공식 zero-shot VC/SVC | CUDA 경로 제공, 8GB VRAM 검증 필요 | 동등 조건 검증 필요 | source·style/timbre reference 구조는 적합하나 대형 toolkit | 상업 사용 불가, 별도 허가 필요 |

## 공식 문서 Coverage

문서 품질은 설치, inference, 모델/가중치, 평가, Server/API 문서의 존재 여부만으로 분류했다. 설명의 정확성이나 사용 편의성을 추정하지 않는다.

| Provider | Coverage | 확인 내용 |
|---|---|---|
| Seed-VC | 높음 | 설치·CLI/WebUI·모델표·SVC 옵션·공식 평가 문서, archive 상태 |
| OpenVoice V2 | 보통 | 설치·Notebook·Usage·Q&A·demo, 제품 Server 문서는 제한적 |
| CosyVoice | 높음 | 설치·모델·inference·FastAPI·streaming·training·deployment 문서 |
| Fish Speech | 높음 | 다국어 문서·API/Server·deployment·training 문서 |
| RVC | 보통 | 다국어 UI·설치·training Wiki, component/가중치 권리 추적은 복잡 |
| Amphion Vevo2 | 보통 | toolkit 설치·checkpoint·inference recipe·논문, Backend 운영 문서는 제한적 |

## 후보별 판단

### Seed-VC

장점은 공식 zero-shot SVC, 1~30초 reference, F0 경로가 현재 `VoiceConverter` 계약과 직접 일치하고 유일하게 RTX 3060 Ti 반복 검증을 마쳤다는 점이다. 단점은 archive, GPL 배포 경계, clipping 위험, 미완료 사용자 평가다. 기술 가치 때문에 Experimental로 유지한다.

### OpenVoice V2

MIT, native Korean, zero-shot tone-color conversion과 큰 Community가 장점이다. 공식 README는 speech/TTS voice cloning을 설명하며 노래 입력 지원을 명시하지 않는다. Singing Provider로 가정하지 않고 현재 역할에서는 Rejected로 분류한다. 공식 SVC 지원이 추가되면 재검토할 수 있다.

### CosyVoice

Apache-2.0, native Korean, 활발한 개발, 공식 Server·streaming 문서가 강점이다. 그러나 최신 공식 설명은 text 기반 multilingual TTS이며 DohaMusic의 `vocals.wav + reference.wav` SVC 계약을 충족한다는 근거가 없다. Voice Conversion 표준 Provider에서는 Rejected이며 향후 TTS/Lyrics 단계 후보와는 별개다.

### Fish Speech

활발한 개발과 한국어 TTS가 장점이다. 직접 SVC가 확인되지 않고 Fish Audio Research License는 상업 SaaS·API·내부 업무를 포함한 상업 목적에 별도 서면 계약을 요구한다. 현재 Voice Conversion Provider에서는 Rejected다.

### RVC

MIT core, 활발한 개발, 큰 Community와 F0 기반 AI singer workflow가 장점이다. 공식 문서는 권장 10분 정도의 저잡음 음성으로 사용자별 모델·feature index를 학습하는 구조를 설명한다. 이는 zero-shot reference 계약과 Phase 4.6의 학습 제외 범위에 맞지 않는다. 운영 fallback이 아니라 **Secondary 평가 후보**로만 선정한다.

### Amphion Vevo2

공식 zero-shot style-preserved/style-converted SVC, Korean metadata, 활발한 upstream은 기술적으로 가장 강한 대안이다. 그러나 공식 가중치가 CC BY-NC-ND 4.0이라 상업 플랫폼 표준이 될 수 없다. 별도 상업 허가 또는 허용 라이선스 가중치가 나오기 전까지 Experimental 연구 후보로만 둔다.

## 라이선스 시나리오

| Provider | 비상업 평가 | 상업 SaaS | Docker 배포 | 온프레미스·모델 배포 |
|---|---|---|---|---|
| Seed-VC GPL-3.0 | 가능 | 법률 검토 후 조건부 | GPL 대응 소스·고지 검토 | GPL 대응 소스·고지 검토 |
| OpenVoice MIT | 가능 | 가능 | 저작권·허가 고지 필요 | 저작권·허가 고지 필요 |
| CosyVoice Apache-2.0 | 가능 | 가능 | LICENSE·NOTICE·변경 고지 검토 | LICENSE·NOTICE·특허 조항 검토 |
| Fish Audio Research License | 가능 | 별도 서면 계약 필요 | 별도 계약 필요 | 별도 계약 필요 |
| RVC MIT core | 가능 | 구성요소·학습 데이터 검토 후 조건부 | 전체 의존성·모델 고지 검토 | 사용자 모델·데이터 권리 포함 검토 |
| Vevo2 CC BY-NC-ND 4.0 weights | 비상업 범위에서 가능 | 불가 | 상업 배포 불가 | 상업 배포 불가 |

이 표는 공식 표시를 기술적으로 분류한 것이며 법률 자문이 아니다. 실제 배포 전에는 고정 버전의 코드, 가중치, vocoder, encoder, 학습 데이터와 의존성 inventory를 다시 검토한다.

## 최종 분류

| 분류 | Provider | 이유 |
|---|---|---|
| Primary | **미선정** | 직접 SVC·계약 적합성·상업 라이선스·8GB 실측·사용자 품질 게이트를 모두 통과한 후보 없음 |
| Secondary | **RVC** | 직접 VC/Singing workflow와 permissive core가 있으나 사용자별 학습 구조 검증 필요 |
| Experimental | **Seed-VC, Amphion Vevo2** | Seed-VC는 유일한 로컬 실측, Vevo2는 유망한 zero-shot SVC지만 각각 archive/GPL·NC 가중치 제약 |
| Rejected | **OpenVoice V2, CosyVoice, Fish Speech** | 현재 공식 범위에서 직접 Singing VC 근거가 없거나 상업 라이선스가 부적합 |

`Rejected`는 해당 프로젝트 전체의 품질을 부정하는 의미가 아니라 DohaMusic Phase 4의 직접 Singing Voice Conversion 역할에 대한 판정이다.
