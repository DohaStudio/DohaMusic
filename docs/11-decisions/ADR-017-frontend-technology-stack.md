# ADR-017 — Frontend Technology Stack

> 상태: [검토 필요]
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 Doha Studio F0
> 관련 문서: [Frontend Architecture](../03-architecture/frontend-architecture.md), [Responsive Guide](../03-architecture/responsive-guide.md), [Frontend Roadmap](../../planning/frontend-roadmap.md)

## 배경

PR #16에서 Responsive Premium Studio의 구조와 UI/UX를 설계했지만 실제 Frontend package와 라이브러리는 확정하지 않았다. 구현 브랜치마다 임의의 선택을 하면 bundle·접근성·상태 경계·테스트 방식이 분산될 수 있다.

## 문제

현재 규모에 필요한 최소 stack을 선택하면서 장기 유지보수, 접근성, bundle 크기, OpenAPI 계약, 테스트 용이성과 도입 비용을 균형 있게 결정해야 한다. F0 계약 검증 전에는 라이브러리 설치로 결정을 선점해서는 안 된다.

## 결정 상태

이 ADR은 후보와 평가 기준을 승인하는 초안이며 최종 기술 선택은 `[검토 필요]`다. F0에서 버전·공식 문서·라이선스·bundle·호환성을 확인한 뒤 상태를 갱신한다. 그전에는 Frontend 프로젝트를 생성하거나 구현 브랜치에서 임의로 의존성을 추가하지 않는다.

## 결정 대상과 후보

| 영역 | 후보 | 장점 | 단점·도입 비용 | 1차 판단 |
|---|---|---|---|---|
| Framework | Next.js App Router | route/layout/loading/error와 responsive web 단일 코드베이스 | Server/Client 경계 학습·운영 복잡도 | 우선 후보 |
| Language | TypeScript | API DTO·상태 union·refactor 안전성 | 설정·type 관리 비용 | 우선 후보 |
| Styling | Tailwind CSS | token 기반 속도·일관성·responsive utility | class 밀도·upgrade·design abstraction 필요 | 검토 |
| Styling | CSS Modules | 표준 CSS 격리·낮은 runtime | token·variant 반복 가능 | 검토 |
| Styling | CSS-in-JS/기타 | 동적 theme 편의 | runtime·bundle·RSC 호환성 비용 | 근거 전 보류 |
| Client state | Zustand | Studio draft·Player에 작은 API와 선택적 구독 | 별도 상태 규칙 필요 | 우선 후보 |
| Client state | React Context | 의존성 없음·단순 global | 잦은 update·scope 확장 시 rerender/구조 복잡 | 제한적 후보 |
| Server state | TanStack Query | cache·polling·retry·invalidation 성숙 | bundle·Provider·학습 비용 | 우선 후보 |
| Server state | 자체 fetch hook | 의존성·추상화 최소 | polling·cache·race·retry를 직접 유지 | 작은 범위 대안 |
| Form | React Hook Form | 성능·field state·접근성 연결 생태계 | schema adapter와 pattern 학습 | 우선 후보 |
| Validation | Zod | runtime 검증·form schema·type 추론 | OpenAPI schema와 중복 가능 | 검토 |
| API Types | OpenAPI type generation | 실제 계약 기반·drift 탐지 | generator·CI·nullable 변환 정책 필요 | F0에서 결정 |
| Icons | Lucide 등 tree-shakable library | 일관된 stroke·접근성 wrapper 용이 | 고유 icon·bundle audit 필요 | 후보 비교 |
| Motion | Framer Motion/Motion 계열 | orchestration·gesture·reduced motion 도구 | bundle·Client Component 범위 증가 | 선택 도입 검토 |
| Unit | Vitest | 빠른 TS/Vite 생태계 | Next 환경 차이 설정 | 우선 후보 |
| Component | React Testing Library | 사용자 행동·접근성 중심 | 복잡 media/motion mock 비용 | 우선 후보 |
| E2E | Playwright | browser matrix·trace·responsive 검증 | CI runtime·fixture 관리 | 우선 후보 |
| Package manager | npm·pnpm | npm은 기본성, pnpm은 disk·workspace 효율 | lockfile·팀 도구 통일 필요 | 하나로 고정 필요 |
| Lint·Format | ESLint·Prettier 또는 대안 | 자동 품질 gate | rule 충돌·upgrade 관리 | repo 표준 결정 필요 |
| Storybook | 도입/미도입 | component state·접근성·visual review | build·maintenance·addon 비용 | F1 전 비용 판단 |
| PWA | 도입/미도입 | installable mobile web·cache 가능성 | offline 음악·민감 data·cache 정책 복잡 | 별도 승인 전 보류 |

## 평가 기준

1. 현재 프로젝트 규모에 과도하지 않은가
2. 장기 유지보수와 upgrade 경로가 명확한가
3. keyboard·screen reader·reduced motion 구현을 돕는가
4. 초기·route bundle과 Client Component 범위를 통제할 수 있는가
5. API polling·form·media·responsive UI 테스트가 쉬운가
6. 라이선스와 공급망 검토가 가능한가
7. 팀이 lockfile·version·lint·CI를 재현할 수 있는가

## 제안 조합과 미확정 사항

현재 규모의 1차 검토 조합은 Next.js App Router + TypeScript, Tailwind 또는 CSS Modules, Zustand, TanStack Query, React Hook Form, Zod, OpenAPI type generation, tree-shakable icon, 선택적 motion, Vitest + React Testing Library + Playwright다. 이는 채택 결정이 아니며 bundle·버전·RSC 호환성·접근성·도입 비용 검증이 남았다.

## 재검토·완료 조건

- `/openapi.json`과 DTO 생성 전략이 검증됨
- styling·state·form·motion 후보의 최소 prototype 없이도 공식 근거 또는 별도 실험으로 trade-off가 기록됨
- package manager·lockfile·lint·format·test command가 확정됨
- Storybook·PWA의 포함/제외와 이유가 기록됨
- 라이선스·bundle·접근성·CI 비용 검토 후 하나의 stack이 승인됨

## 관련 PR

- 문서 정합성 PR: 생성 후 연결 필요
