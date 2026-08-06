# VALIDATION-VOICE-ENROLLMENT: F6 Guided Voice Enrollment

> 문서 상태: [자동 검증 완료 / 실제 기기 수동 검증 필요]
> 검증일: 2026-08-02
> 기준 브랜치: `develop` (`7a6884ee1d671112e60d0375e07915d4c4abf988`)
> 작업 브랜치: `test/voice-enrollment-validation`
> 관련 문서: [운영·수동 검증 체크리스트](../../docs/10-operations/voice-enrollment-operations-checklist.md), [Frontend Roadmap](../../planning/frontend-roadmap.md), [요구사항](../../docs/02-requirements/voice-enrollment-requirements.md)

## 1. 목적과 판정 범위

Voice Enrollment의 제품 기능·API·DB를 변경하지 않고 신규 사용자, 녹음, 품질 경고, 실패·재시도·만료·취소·cleanup 흐름을 자동 검증한다. 실제 개인 음성은 저장하거나 업로드하지 않았다. 실제 사용자 마이크·Bluetooth 장치와 실제 Android/iOS 하드웨어는 이번 실행 환경에서 사용할 수 없으므로 수동 체크리스트로 남긴다.

판정은 다음 두 층으로 분리한다.

- `[자동 검증 완료]`: 합성 파일·합성 MediaStream과 API mock, 기존 Backend 회귀로 결정적으로 재현 가능한 계약
- `[수동 검증 필요]`: 실제 마이크 권한·음질·장치 연결, 실제 Android Chrome·iOS Safari의 recorder MIME과 사용자 체감 UX

## 2. 테스트 환경

| 항목 | 환경 |
|---|---|
| OS | Windows NT 10.0.26200.0, x64 |
| Node.js / npm | 24.15.0 / 11.12.1 |
| Next.js / Playwright | 16.2.12 / 1.62.1 |
| Chrome | 설치 채널 150.0.7871.187 |
| Edge | 설치 채널 150.0.4078.105 |
| Firefox | Playwright Firefox 153.0 (`firefox-1538`) |
| Pixel 7 | Playwright device descriptor + desktop Chromium 엔진 |
| iPhone 14 | Playwright device descriptor + Windows WebKit 26.5 (`webkit-2336`) |
| Backend | Python 3.12.5, 저장소 `.venv`, SQLAlchemy 2.0.51 |
| FFmpeg | 현재 PowerShell PATH에는 없음. 미설치 오류 자동 test와 기존 Ubuntu·Windows FFmpeg CI 결과를 구분해 사용 |

Chrome·Edge는 설치된 실제 desktop 실행 파일로 headless E2E를 수행했다. Firefox는 Playwright 제공 브라우저, Pixel 7과 iPhone 14는 viewport·user agent·touch를 에뮬레이션한 결과다. 모바일 에뮬레이션은 실제 OS의 microphone stack이나 codec을 검증하지 않는다. Codex in-app Browser는 세션에 사용 가능한 tab이 없어 별도 수동 시각 검증을 수행하지 못했다.

## 3. 시나리오 결과

| 시나리오 | 결과 | 근거와 경계 |
|---|---|---|
| 신규 사용자 동의 → WAV upload → PASS → 대표 Sample → Profile | PASS | 5개 Playwright 프로젝트에서 완료, idempotency header·Profile 선택 확인 |
| MediaRecorder → preview → upload | PASS(합성) | 실제 Chrome MediaRecorder와 Web Audio 합성 stream으로 5초 녹음·Blob preview·multipart upload 확인. 실제 microphone은 미검증 |
| LOW_VOLUME | PASS | 경고 문구, 확인 전 다음 단계 disabled, 확인 후 enabled |
| HIGH_SILENCE_RATIO | PASS | 동일 |
| POSSIBLE_CLIPPING | PASS | 동일 |
| 5초 미만 / 60초 초과 | PASS | Backend 오류 code를 사용자 안전 문구로 mapping |
| 손상 파일 / 지원 안 되는 media | PASS | decode 실패 UX와 unsupported 확장자 client 선차단 확인 |
| WebM + FFmpeg 없음 | PASS | `503` + `VOICE_NORMALIZER_UNAVAILABLE` UX; Backend 자동 test는 환경과 격리 |
| timeout | PASS(오류 UX) | `REQUEST_TIMEOUT` 응답 mapping 확인. 실제 90초 network timeout 체감은 수동 대상 |
| duplicate upload | PASS | 실패 후 retry가 동일 `Idempotency-Key` 사용, Sample 1개로 수렴 |
| duplicate submit | PASS, 관찰 사항 있음 | 빠른 double-click은 HTTP 요청 2건을 만들지만 동일 key를 사용하고 Backend replay 계약으로 Profile 1개에 수렴 |
| expired enrollment | PASS | 복원 ID 제거, sessionStorage 정리, 새 등록 안내 |
| cancel / cleanup | PASS | cancel 후 `PENDING` 사용자 안내와 새 등록 복귀; cleanup retry·완료는 Backend maintenance test가 담당 |
| partial delete / missing / duplicate delete / crash recovery | 기존 자동 검증 확인 | `test_voice_enrollment_maintenance.py`와 Storage test에 존재. 이번 로컬 집중 실행은 환경 시간 한도로 완료 전 종료 |

## 4. Browser Matrix

| Browser / Device | 녹음 | Upload | Submit | Notes |
|---|---|---|---|---|
| Chrome 150 desktop | PASS(합성 stream) | PASS | PASS | 설치된 Chrome 채널. 실제 microphone·권한 prompt는 미검증 |
| Edge 150 desktop | MIME probe PASS | PASS | PASS | 설치된 Edge 채널. 실제 microphone 녹음은 수동 대상 |
| Playwright Firefox 153 | MIME probe PASS | PASS | PASS | 실제 Firefox 엔진, 실제 microphone은 미검증 |
| Pixel 7 emulation | 엔진 probe PASS | PASS | PASS | desktop Chromium device emulation; 실제 Android가 아님 |
| iPhone 14 emulation | 미지원으로 관찰 | PASS | PASS | Windows Playwright WebKit에는 `MediaRecorder` 없음; 실제 iOS Safari 판정으로 사용 금지 |
| Safari desktop | 미검증 | 미검증 | 미검증 | macOS 실제 기기 필요 |

## 5. MIME Matrix

실행 시 `MediaRecorder.isTypeSupported()`와 합성 audio stream으로 실제 생성된 `Blob.type`을 함께 기록했다. `isTypeSupported()`는 사용자 agent가 녹음 가능하다고 판단하는 값이며 자원 부족 등으로 실제 녹음은 여전히 실패할 수 있다([MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static)).

| Browser / Device | 확인 결과 | 실제 Blob type | 판정 |
|---|---|---|---|
| Chrome 150 desktop | WebM Opus 지원, WAV/Ogg 미지원 | `audio/webm;codecs=opus` | 실제 설치 채널에서 확인 |
| Edge 150 desktop | WebM Opus 지원, WAV/Ogg 미지원 | `audio/webm;codecs=opus` | 실제 설치 채널에서 확인 |
| Playwright Firefox 153 | WebM Opus와 Ogg Opus 지원, WAV 미지원 | 우선순위에 따라 `audio/webm;codecs=opus` | Playwright Firefox에서 확인 |
| Pixel 7 emulation | desktop Chromium과 동일 | `audio/webm;codecs=opus` | 실제 Android MIME으로 간주 금지 |
| iPhone 14 WebKit emulation | `MediaRecorder` 없음 | 없음 | Windows WebKit port 결과이며 실제 iOS Safari가 아님 |
| Safari desktop | 미확인 | 미확인 | 실제 macOS 필요 |
| Android Chrome | 미확인 | 미확인 | 실제 Android 필요 |
| iOS Safari | 미확인 | 미확인 | 실제 iPhone 필요 |

WebKit 공식 문서는 Safari 18.4에서 WebM/Opus MediaRecorder 지원을 추가했다고 설명하고, Safari 26.0에서는 ALAC·PCM 지원 추가를 기록한다([Safari 18.4](https://webkit.org/blog/16574/webkit-features-in-safari-18-4/), [Safari 26.0](https://webkit.org/blog/17333/webkit-features-in-safari-26-0/)). 이는 이번 Windows WebKit 결과나 실제 iOS 기기 MIME을 대신하지 않으므로 제품 Matrix에는 미확인으로 유지한다.

## 6. Known Issue와 Limitation

- FFmpeg가 없으면 WAV 이외 WebM/Ogg 입력은 `503 VOICE_NORMALIZER_UNAVAILABLE`로 거부된다.
- 빠른 submit double-click은 동일 idempotency key를 가진 요청 2건을 전송할 수 있다. Backend replay로 중복 Profile은 방지되지만 불필요한 요청 억제는 후속 UX 개선 후보다.
- 실제 Safari, iOS Safari, Android Chrome, Bluetooth microphone과 장치 전환을 검증하지 않았다.
- Playwright mobile device는 viewport·입력 특성 에뮬레이션이며 실제 mobile media stack 검증이 아니다.
- 기본 품질 검사는 음량·무음·clipping의 휴리스틱이며 Voice Provider 적합성이나 AI 음색 변환 품질을 보장하지 않는다.
- upload resume와 동의 철회는 지원하지 않는다.
- scheduler와 metric은 process-local이다. 다중 replica 운영에는 lease·외부 Queue·영속 observability가 필요하다.
- Phase 9 인증·소유권·감사·rate limit이 없어 공개 운영 준비 완료 상태가 아니다.
- F6 Sample은 Phase 7 Dataset에 자동 연계되지 않는다.

## 7. 운영 준비도

| 항목 | 상태 |
|---|---|
| Backend | [구현 완료 / 집중 회귀 재확인 필요] |
| Frontend | [자동 검증 완료] |
| Scheduler | [로컬 단일 process 구현 완료] |
| Storage | [로컬 Storage 구현 완료 / 운영 writable·disk 점검 필요] |
| FFmpeg | [CI 검증 완료 / 현재 shell 미설치 / 운영 설치 확인 필요] |
| Testing | [브라우저 Matrix 자동 검증 완료 / 실제 기기 수동 검증 필요] |
| Documentation | [완료] |
| Monitoring | [기본 log·process-local metric / 장기 monitoring 미구현] |
| Authentication | [Phase 9 선행] |
| Dataset | [Phase 7 미연계] |

## 8. 실행 명령과 결과

```powershell
cd frontend
npm run typecheck
npm run lint -- playwright.validation.config.ts tests/e2e/voice-enrollment-validation.spec.ts
npm run build
npm run test:e2e:voice-validation

cd ..
.venv\Scripts\python.exe -m pytest -q --basetemp D:\DohaMusic\.pytest-tmp-validation
```

- TypeScript: PASS
- ESLint: PASS
- Next production build: PASS. 첫 sandbox 실행은 Google Fonts network 차단, 승인된 network 재실행 통과
- Voice Playwright Matrix: 34 pass, 56 의도적 skip. 상세 오류 UX는 Chrome 대표 프로젝트에서 실행하고 정상 등록·만료·MIME은 5개 프로젝트에서 실행
- 기존 Playwright 전체 회귀: 28 pass
- Backend 전체: 기본 Temp는 기존 사용자 Temp 접근 권한으로 setup 실패. 저장소 내부 `--basetemp` 재실행은 10분에 약 60%까지 오류 없이 진행했으나 로컬 시간 한도로 종료
- Backend F6 집중: API 7 pass/1 skip, Audio 9 pass/4 skip, maintenance+repository 12 pass, migration 2 pass로 합계 30 pass/5 skip
- Backend skip 5개: 현재 PATH에 실제 FFmpeg가 없어 설치 환경 WebM/Ogg 통합 경로를 건너뜀. FFmpeg 미설치·timeout·비정상 종료·격리 테스트는 통과했으며 설치 환경 결과는 기존 Ubuntu·Windows CI 이력과 PR check 상태를 구분해 확인
- `ruff check backend`: FAIL(기준선). 이번 변경과 무관한 Audio Analysis·K-POP import/`__all__` 정렬 11건이며 Backend 변경 0개이므로 이 PR에서 수정하지 않음
- `git diff --check`: PASS
- 실제 개인 음성·실제 microphone·GPU·외부 서비스 test: 실행하지 않음

## 9. F6 상태 재평가

F6는 `[진행 중]`을 유지한다. 구현과 결정적 자동 Validation은 완료됐지만, 완료 기준에 포함된 사용자 동의 실제 마이크 평가와 실기기 MIME이 없고 공개 운영에는 Phase 9 항목도 남아 있다. 이번 PR로 상태를 과장하지 않고 다음 근거를 추가한다.

- 자동 E2E Validation: 완료
- Desktop Chrome·Edge 설치 채널 및 Firefox 엔진 upload/submit: 완료
- Pixel 7·iPhone 14 responsive emulation: 완료
- 실제 사용자 마이크·실제 Android/iOS·Bluetooth: 미완료
- 공개 운영 인증·소유권·분산 scheduler/monitoring: Phase 9 선행

## 10. 남은 작업

1. 개인 음성을 저장소에 남기지 않는 실제 사용자 마이크 수동 평가
2. 실제 Android Chrome·iOS Safari·macOS Safari MIME/권한/preview 검증
3. Bluetooth·장치 연결 해제와 장치 전환 검증
4. Phase 9 인증·소유권·동의 철회·다중 replica 운영 설계
5. Phase 7 Dataset은 별도 opt-in·lineage 정책 승인 후에만 연계
