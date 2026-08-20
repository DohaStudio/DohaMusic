# Navigation Guide

> 분류: [STALE / Authority 아님]
> 현재 기준: [Frontend Overview](frontend-overview.md), [실제 App Router](../../frontend/app)
> 안내: 계획 navigation은 현재 route tree와 대조하기 전 구현 사실로 사용하지 않는다.

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 문서: [Page Structure](page-structure.md), [Responsive Guide](responsive-guide.md)

## Primary Navigation

| Label | Route 역할 | 상태 |
|---|---|---|
| Studio | 현재 곡 제작 workspace | 설계 가능 |
| Lyrics Lab | 가사 생성·검증·revision | API 지원 |
| Voice | 동의 profile 관리 | API 부분 지원 |
| My Projects | 생성 이력·프로젝트 | 목록 API 선행 필요 |
| Settings | UI 설정·Backend health | 부분 지원 |

Landing, About은 marketing navigation에 둔다. Generation과 Result는 Job context route이며 primary navigation에 고정하지 않는다.

## Desktop·Mobile 차이

- Desktop: label이 있는 216px sidebar, active item은 accent rail·surface·icon으로 3중 표시한다.
- Tablet: icon rail + tooltip/accessible label, workspace 안 breadcrumb 사용.
- Mobile: Studio·Lyrics·Voice·Projects·Settings의 bottom navigation. 최대 5개를 유지한다.
- 생성 진행 중에는 mini status pill을 shell에 유지해 다른 화면에서도 Job으로 돌아갈 수 있게 한다.

## Context Navigation

- Studio timeline: 작업 section 간 이동. 완료 여부와 데이터 validity를 구분한다.
- Breadcrumb: Settings/About 같은 깊은 페이지보다 Job context에서 `Studio / Generation / {short id}`로 사용한다.
- Back: browser history를 존중하며 destructive draft loss가 있으면 확인한다.
- Deep link: `/generation/{jobId}`, `/result/{jobId}`는 URL만으로 API 상태를 복원한다.

## 상태와 권한

현재 인증·소유권이 없으므로 사용자 avatar, plan, private library를 실제 계정 기능처럼 표현하지 않는다. 첨부 레퍼런스의 profile 영역은 향후 shell 자리로만 설계한다. Projects와 download는 필요한 API가 생길 때까지 명확히 비활성화한다.

## 404와 오류 이동

- 알 수 없는 route는 404에서 Studio·Landing으로 이동할 수 있다.
- 존재하지 않는 Job은 일반 404와 구분해 Job ID와 안전한 복귀 action을 제공한다.
- 오류 상태가 navigation 전체를 막지 않도록 App shell은 유지한다.
