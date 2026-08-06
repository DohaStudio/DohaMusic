# Doha Studio Design System

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 문서: [Frontend Overview](frontend-overview.md), [UI Component Guide](ui-component-guide.md), [Responsive Guide](responsive-guide.md), [디자인 레퍼런스 정책](design-reference-policy.md)

첨부 Vinyl Music Dashboard는 방향 참고 자료이며 원본 UI·브랜드·artwork를 복제하거나 서비스 자산으로 사용하지 않는다. 모든 token과 component는 DohaMusic 고유 체계로 재해석하며 세부 기준은 [디자인 레퍼런스 정책](design-reference-policy.md)을 따른다.

## Color System

| Token | 값 | 용도 |
|---|---|---|
| `background` | `#111111` | App 전체 배경 |
| `surface-1` | `#1B1B1B` | 기본 card·panel |
| `surface-2` | `#242424` | elevated card·hover |
| `surface-glass` | `rgba(27,27,27,.78)` | blur 가능한 overlay |
| `accent` | `#E53935` | primary action·active·progress |
| `accent-hover` | `#F04B47` | hover |
| `accent-pressed` | `#C62828` | pressed |
| `warm-beige` | `#D8C2A6` | artwork·premium secondary emphasis |
| `text-primary` | `#FFFFFF` | 제목·핵심 값 |
| `text-secondary` | `#A7A7A7` | 설명·metadata |
| `text-muted` | `#737373` | disabled·보조 |
| `border` | `rgba(255,255,255,.10)` | card·divider |
| `success` | `#57B77A` | 완료 |
| `warning` | `#D9A441` | 검토·경고 |
| `error` | `#F05B61` | 실패 |

텍스트와 interactive state는 WCAG AA 대비를 확인한다. Accent를 긴 본문 텍스트로 사용하지 않는다.

## Typography

- 기본: 시스템 한국어 sans-serif stack. 브랜드용 custom font는 라이선스·성능 검토 후 확정한다.
- Display: 48/56, 700; Page title: 32/40, 700; Section: 24/32, 650.
- Card title: 18/26, 600; Body: 15/24, 400; Label: 13/18, 600; Caption: 12/16, 500.
- 숫자 timer·BPM·duration은 tabular numerals를 사용한다.
- Mobile은 Display 36/44, Page title 28/36으로 축소한다.

## Spacing·Grid

- 4px base: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80`.
- Desktop max content 1600px, 12-column grid, gutter 24px.
- Tablet 8-column, gutter 20px. Mobile 4-column, side padding 16px.
- Card 내부 기본 24px, compact 16px, section 간격 32~48px.

## Radius·Shadow·Elevation

| 수준 | Radius | 표현 |
|---|---:|---|
| control | 10px | input·button |
| card | 16px | 일반 panel |
| feature | 24px | artwork·workspace |
| pill | 999px | chip·segmented control |

- Level 0: shadow 없음, border만 사용.
- Level 1: `0 8px 24px rgba(0,0,0,.22)`.
- Level 2: `0 16px 48px rgba(0,0,0,.32)`.
- Glass는 blur 16~24px와 얇은 border를 함께 사용하되 저성능·reduced transparency 환경에서는 불투명 surface로 fallback한다.

## Controls

- Button: Primary(red fill), Secondary(surface), Ghost, Destructive, Icon. 높이 44/48px.
- Input: label을 placeholder로 대체하지 않는다. error·help·counter 영역을 예약한다.
- Card: default, interactive, selected, disabled, skeleton 상태를 갖는다.
- Modal: 짧고 집중된 확인. Mobile에서는 full-height Drawer로 전환 가능하다.
- Drawer: inspector·queue·mobile step summary에 사용한다.
- Toast: 저장·연결 결과 등 비차단 feedback. 오류 복구 action이 필요하면 inline alert를 우선한다.
- Progress: 단계 label + percentage + 상태 설명을 함께 제공한다.

## Music Components

- Waveform: 실제 샘플 기반과 decorative를 구분한다. 실제 audio data가 없으면 “preview unavailable”을 표시한다.
- Player: 검증된 Pipeline WAV의 단일 전역 source, play/pause, scrubber, volume, time과 안전한 오류 상태를 제공한다.
- Artwork: 1:1 기본, 16px 이상 radius, dominant-color ambient glow는 대비를 침해하지 않는다.
- Vinyl: 1:1, groove texture, center label. 회전은 재생/생성 상태와 reduced motion에 연결한다.
- Icon: 20/24px 표준, stroke 스타일 통일, icon-only button에는 accessible name을 제공한다.

## Motion

| 동작 | 시간 | easing/규칙 |
|---|---:|---|
| micro interaction | 120~180ms | ease-out |
| card hover | 180ms | translateY -2px, shadow 1단계 상승 |
| page transition | 240~320ms | opacity + 8px 이동 |
| modal/drawer | 220~300ms | spring-like, overshoot 최소 |
| step change | 240ms | 방향성 있는 crossfade |
| progress | 300ms | 값 감소 animation 금지 |
| vinyl | 상태 기반 | 재생 중 일정 회전, 생성 중 느린 회전 |

Waveform·loading·progress는 무한한 과장 motion을 피하고 상태 의미를 가져야 한다. `prefers-reduced-motion`에서는 회전, parallax, scale hover와 자동 이동을 제거한다.
