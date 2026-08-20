# 배포 가이드

> 문서 목적: 운영 배포 전 필요한 승인 게이트와 절차 범위를 정의한다.
> 현재 상태: **계획 / 배포 미실행**

운영 배포 전 인증·권한, TLS, 비밀 관리, DB 백업·복구, 객체 저장소, 큐 내구성, GPU 격리, 업로드 제한, 동의·삭제 흐름, 로그 마스킹, 모니터링과 롤백을 검증해야 한다.

CURRENT는 로컬 단일 사용자·no-product-login이고 production topology는 미확정이다. 운영 배포 승격 전에는 [Reviewer Authentication 배포 권위](../09-security/reviewer-authentication-deployment-authority.md)의 semantic reviewer population·interaction, upstream identity issuer, service authentication, delegated assertion, recovery·revocation, secret manager와 private mapping store 결정을 완료해야 한다. 이 결정 전에는 DohaAudio authentication Provider를 활성화하지 않는다.

정확한 인프라와 명령은 구현·위협 모델·부하 테스트 뒤에 작성한다. 자동 배포가 저장소에 추가되더라도 문서 작업만으로 실행하지 않는다.

## Voice Provider 배포 게이트

Seed-VC는 `Experimental`·운영 보류다. 현재 상태에서는 운영 기본값, 상용 SaaS, 공개 Preview, Docker·온프레미스 번들에 포함하지 않는다.

배포 검토를 다시 시작하려면 EVAL-003 사용자 승인, clipping/export 회귀 검증, timeout·취소·모니터링 기준, 코드·가중치·의존성의 GPL 준수 목록과 법률 승인, archive upstream 유지보수 계획을 모두 확보해야 한다. GPL의 서버 실행과 외부 사본 배포는 의무가 다를 수 있으므로 배포 형태를 문서화하고 별도로 검토한다.

Phase 4.6 평가에서도 Primary와 Fallback은 미선정이다. RVC는 학습형 Secondary 평가 후보일 뿐 배포 Provider가 아니며, Vevo2는 CC BY-NC-ND 4.0 가중치, Fish Speech는 별도 상업 계약 때문에 상용 배포 대상에서 제외한다. OpenVoice와 CosyVoice는 permissive 라이선스지만 공식 Singing VC 근거가 없어 이 Pipeline에 배포하지 않는다.

Phase 5 Pipeline Orchestrator의 AI 단계는 Mock 기반 개발 검증 상태지만 Phase 5.1 Mixer는 실제 DSP 합성을 수행한다. 인프로세스 ThreadPool은 프로세스 장애 시 Job을 복구하지 않는다. 외부 운영 배포 전 내구성 Queue, idempotency, 취소·timeout 강제 종료, EVAL-004 Mixer 청감 품질, True Peak·loudness 정책, 인증·파일 소유권과 Primary Voice 게이트를 별도로 승인해야 한다.
