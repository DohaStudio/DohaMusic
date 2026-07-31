# Page Structure

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 문서: [Frontend Overview](frontend-overview.md), [Studio UX Flow](studio-ux-flow.md), [Navigation Guide](navigation-guide.md)

페이지 기능 상태는 [Frontend 지원 범위](frontend-overview.md#frontend-지원-범위)의 `Available`, `Partial`, `Backend Required`, `Planned`를 사용한다.

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

- 목적: 명시적 동의가 있는 profile metadata 관리.
- 구성: consent notice, create metadata form, current-session cards, delete confirmation.
- API: `POST`, `DELETE /api/voice-profiles`는 `Partial`; list/get/upload는 `Backend Required`임을 empty state에 명시.

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
