# Page Structure

> 문서 상태: [보관]
> 분류: [HISTORICAL / Authority 아님]
> 보관 사유: CURRENT route와 TARGET Workspace가 혼재된 Phase 8 page 초안을 현재 Navigation에서 분리했다.
> 대체 문서: [Frontend Architecture](../../03-architecture/frontend-architecture.md), [Frontend Overview](../../03-architecture/frontend-overview.md), [AI-native DAW 전환 계획](../../../planning/ai-native-daw-frontend-migration.md)
> Archived at: 2026-08-20
> 최종 수정일: 2026-08-01
> 관련 문서: [Frontend Overview](../../03-architecture/frontend-overview.md), [Studio UX Flow](../../03-architecture/studio-ux-flow.md), [Navigation Guide](navigation-guide.md)

페이지 기능 상태는 [Frontend 지원 범위](../../03-architecture/frontend-overview.md#frontend-지원-범위)의 `Available`, `Partial`, `Backend Required`, `Planned`를 사용한다.

## Landing

- 목적: “음악을 만드는 공간”이라는 가치와 안전한 개인 창작 흐름 전달.
- 구조: immersive vinyl hero, 핵심 Workflow, capability/제약, CTA, 안전·권리.
- API: 선택적 `GET /health`; Backend 미연결이어도 정적 내용은 렌더링.

## Studio

- 목적: Music Settings, Lyrics, Voice, Review를 하나의 작업 공간에서 구성.
- Desktop: Sidebar / Workspace / Inspector / Transport.
- Mobile: current step / focused content / sticky action / bottom nav.
- API: `POST /api/lyrics`, `/validate`, `POST /api/voice-profiles`, `POST /api/pipelines`.

## Lyrics Lab

- 목적: 가사 생성, 직접 작성 검증, 조회, revision, 삭제.
- 구성: structured editor, input inspector, validation panel, version context.
- API: Lyrics API 전체. Provider가 지원하지 않는 revision action은 비활성.

## Voice

- 목적: 명시적 동의가 있는 Voice Profile의 안내형 등록·목록·선택·삭제.
- 현재 구성: 안내 → 동의 → 방법 → 녹음/업로드 → 품질 → 대표 Sample → Profile 확인 → 완료 Wizard, Profile list·선택·삭제, 기존 빠른 WAV fallback과 개발 플래그의 path create.
- 현재 API: Enrollment 7개 endpoint와 기존 Profile upload·list·get·delete가 로컬 MVP에서 `Available`; 서버 음성 preview content와 인증·소유권은 제공하지 않는다.
- F6 Frontend `[완료]`: MediaRecorder feature detection, 권한·일시정지·재개·60초 자동 종료, 입력 수준·메모리 preview, 최대 10개 upload, session 복원·취소·만료·멱등 재시도와 Studio 선택을 구현했다. 합성 WebM/Ogg의 Backend FFmpeg 정규화는 Windows/CI에서 검증했고 실제 마이크·기기별 MIME 평가는 남아 있다.
- Voice Enrollment UI: 정상 안내와 오류를 분리하고 녹음 상태·입력 수준·안내 문장, Sample별 품질·재생·대표 선택·삭제, 우측 Summary, 완료 CTA를 Desktop·Tablet·Mobile 반응형으로 제공한다.
- 세부 요구사항: [Voice Enrollment](../../02-requirements/voice-enrollment-requirements.md).

## Generation Progress

- 목적: 음악 제작 단계와 연결 상태를 신뢰 가능하게 전달.
- 구성: large vinyl status, step timeline, progress, technical inspector, safe error.
- API: `GET /api/pipelines/{jobId}` polling. cancel/retry API는 없음.

## Result

- 목적: 완료 설정과 품질 metadata, 결과 file inventory 검토.
- 구성: artwork/vinyl, disabled-or-active player, track info, quality panel, remake action.
- API: Pipeline Job + files metadata는 `Available`. 오디오 content streaming/download는 `Backend Required`다.

## Settings

- 목적: theme, reduced motion, polling preference, Backend health와 문서 링크.
- 계정·결제·API key 저장 UI는 현재 범위가 아니다.

## About

- 목적: 프로젝트 목표, AI 생성 사실, Provider/모델 투명성, 라이선스·음성 동의 정책 연결.
- 정적 페이지이며 지원하지 않는 상업 배포 상태를 주장하지 않는다.

## 404

- 목적: 길을 잃은 사용자를 안전하게 Studio/Landing으로 복귀.
- vinyl label이 비어 있는 visual을 사용할 수 있으나 motion은 reduced-motion을 따른다.

## 페이지 상태 공통표

모든 data page는 `initial`, `loading`, `content`, `empty`, `error`, `offline/reconnecting`을 정의한다. 비동기 Job page는 여기에 `queued`, `running`, `completed`, `failed`를 추가한다. Skeleton은 실제 layout을 반영하고 무기한 loading 대신 연결 상태를 알린다.
