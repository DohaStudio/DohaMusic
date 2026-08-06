# ADR-017 — Frontend Technology Stack

> 상태: [승인]
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 Doha Studio MVP
> 관련 문서: [Frontend Architecture](../03-architecture/frontend-architecture.md), [Responsive Guide](../03-architecture/responsive-guide.md), [Frontend Roadmap](../../planning/frontend-roadmap.md)

## 배경

Responsive Premium Studio 설계를 실제 Frontend로 전환하려면 framework, 상태 경계, form, API 계약, styling과 검증 도구를 하나의 재현 가능한 조합으로 고정해야 한다.

## 문제

Desktop·Tablet·Mobile Web을 단일 코드베이스로 제공하면서 FastAPI 계약 drift, 비동기 Pipeline polling, session draft, 접근성과 과도한 runtime 의존성을 함께 관리해야 한다.

## 결정

| 영역 | 선택 | 버전·방식 |
|---|---|---|
| Package manager | npm | npm 11, `package-lock.json` 고정 |
| Framework | Next.js App Router | `16.2.12` |
| UI runtime | React | `19.2.8` |
| Language | TypeScript | strict, `5.9.3` |
| Styling | CSS design token + 역할별 semantic CSS | token·base·page·layout·component·responsive 분리, runtime CSS-in-JS·Tailwind 미도입 |
| Client state | Zustand | Studio draft `sessionStorage`, Settings `localStorage` allowlist persist |
| Server state | TanStack Query | API cache·mutation·adaptive polling |
| Form | React Hook Form | Studio settings schema form |
| Validation | Zod | Client form 제약; Backend Pydantic가 최종 권위 |
| API types | 수동 DTO + mapper + 계약 테스트 | OpenAPI 자동 생성은 후속 검토 |
| Icon | Lucide React | tree-shakable SVG icon |
| Motion | CSS transition·keyframe | `prefers-reduced-motion`와 사용자 설정으로 정지 |
| Unit·Component | Vitest + React Testing Library | jsdom |
| E2E | Playwright | Chromium Desktop·Pixel 7 viewport |
| Lint·format | ESLint 9 + Next Core Web Vitals | 별도 formatter 의존성 미도입 |

Next.js rewrite가 `/backend/*`를 server-only `DOHAMUSIC_API_ORIGIN`으로 전달한다. 기본 브라우저 Base URL은 `/backend`이므로 Backend CORS 설정을 변경하지 않는다. caller 취소와 timeout signal은 `AbortSignal.any()`로 결합한다. 이 API는 Node.js 공식 문서상 v18.17.0·v20.3.0부터 제공되며 현재 Node 24 type/build와 Playwright Chromium 검증 범위에 포함된다.

## 선택 이유

- App Router가 route, layout, loading, error, 404 경계를 한 코드베이스에서 제공한다.
- Zustand는 Studio draft에만 사용하고 TanStack Query를 서버 상태의 진실 원천으로 유지한다.
- CSS token은 현재 한 개 theme의 MVP에서 utility framework 의존성을 피하고, 역할별 stylesheet는 큰 단일 파일 없이 반응형·reduced-motion 정책을 유지한다.
- React Hook Form과 Zod는 사용자 입력을 조기에 검증하지만 실제 request DTO 범위는 Pydantic 계약을 따른다.
- 수동 DTO는 현재 API 규모에서 생성 pipeline을 추가하지 않고 시작할 수 있다. 내부 `file_path`는 Backend public response schema에서 제거하고 DTO·mapper 계약 테스트로 회귀를 차단한다.
- reduced motion은 사용자 명시 설정, system preference, 기본값 순이며 실제 구현 값만 저장한다. Studio·Settings persist는 명시 allowlist를 사용하고 비밀·음성 경로·서버 응답을 저장하지 않는다.
- npm override는 직접 기능 의존성을 바꾸지 않고 audit에서 확인된 취약 transitive package의 수정 버전만 lockfile에 고정한다.
- animation 요구는 CSS로 충분하여 Framer Motion을 설치하지 않는다.

## 대안

- Tailwind CSS: 빠른 responsive utility가 장점이지만 현재 token과 variant 규모에는 추가 build 의존성이 필요하지 않아 보류했다.
- CSS Modules: component 격리가 장점이나 App shell 전체 token·layout을 공유하는 MVP에서는 semantic global CSS를 선택했다.
- React Context·custom fetch hook: 의존성은 줄지만 draft persist와 polling·cache lifecycle을 직접 유지해야 해 채택하지 않았다.
- OpenAPI 자동 생성: 계약 drift 방지에 유리하나 generator·CI 정책이 필요해 Backend schema가 확장될 때 재검토한다.
- Framer Motion, Storybook, PWA, Prettier: 현재 완료 기준에 필수적이지 않아 도입하지 않았다.

## 장점과 단점

장점은 API와 client state 경계가 명확하고, Desktop·Mobile E2E 및 production build를 같은 npm 명령으로 재현할 수 있다는 점이다. 단점은 수동 DTO drift 가능성과 semantic CSS selector 범위, `AbortSignal.any()`가 없는 오래된 브라우저, Chromium 외 실제 브라우저 검증이 남는다는 점이다.

## 재검토 조건

- API DTO가 반복적으로 drift하거나 endpoint가 크게 늘어 OpenAPI 생성 비용보다 수동 유지 비용이 커질 때
- 두 개 이상의 theme 또는 독립 UI package가 필요해 CSS Modules·Tailwind 비교가 필요할 때
- 복잡한 timeline·gesture가 승인되어 CSS motion만으로 접근성·유지보수가 어려울 때
- Storybook, PWA, formatter 또는 다중 browser CI가 Phase 8 완료 게이트가 될 때
- 지원 브라우저 범위에 `AbortSignal.any()` 미지원 runtime이 포함될 때 signal merge helper로 교체 검토
- transitive override가 upstream 정식 dependency 범위에 반영되거나 호환성 문제가 발생할 때 제거·갱신

## 관련 PR

- [PR #19](https://github.com/DDORINY/DohaMusic/pull/19) — Doha Studio Responsive Frontend MVP
- [PR #20](https://github.com/DDORINY/DohaMusic/pull/20) — Frontend 보안 경계와 유지보수 구조
- [PR #21](https://github.com/DDORINY/DohaMusic/pull/21) — Audio 재생·다운로드
- PR #22 — Voice Profile upload·list·get·Studio 선택
