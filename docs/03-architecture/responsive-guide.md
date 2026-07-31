# Responsive Guide

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 원칙: Mobile First, content priority before breakpoint
> 관련 문서: [Frontend Overview](frontend-overview.md), [Navigation Guide](navigation-guide.md), [Design System](design-system.md)

## 기준 구간

| 구간 | 기준 폭 | Layout |
|---|---:|---|
| Mobile | 320~767px | 1 column, bottom nav, step header, bottom sheet |
| Tablet | 768~1199px | 2 column 또는 canvas + drawer, compact rail |
| Desktop | 1200px 이상 | sidebar + workspace + inspector, bottom transport |

Breakpoint는 특정 기기명이 아니라 콘텐츠가 충돌하는 지점에서 최종 조정한다.

## Desktop

```text
┌──────────┬──────────────────────────────┬───────────────┐
│ Sidebar  │ Workspace / Vinyl / Timeline│ Inspector     │
│ 216px    │ fluid                        │ 320~380px     │
├──────────┴──────────────────────────────┴───────────────┤
│ Transport / Waveform / Job summary                     │
└─────────────────────────────────────────────────────────┘
```

- Sidebar 고정, workspace가 주 시선, inspector는 context에 따라 접을 수 있다.
- 높이 부족 시 각 column을 독립 scroll하되 focus와 scroll 위치를 잃지 않는다.
- hover는 보강 표현이며 기능 발견의 유일한 방법으로 사용하지 않는다.

## Tablet

- Sidebar는 72px icon rail 또는 top bar로 축소한다.
- Inspector는 360px drawer로 열고 workspace를 가리지 않도록 overlay/side mode를 선택한다.
- Vinyl/Artwork는 viewport의 40~55% 범위로 제한한다.
- Timeline은 horizontal scroll 가능한 step strip이 되며 현재 step을 자동으로 보이게 한다.
- Transport는 하단 full width, volume/queue 같은 2차 제어는 overflow menu로 이동한다.

## Mobile

```text
┌─────────────────────────┐
│ Header + current step   │
├─────────────────────────┤
│ Focused content         │
│ one decision per screen │
├─────────────────────────┤
│ Sticky primary action   │
├─────────────────────────┤
│ Bottom Navigation       │
└─────────────────────────┘
```

- 16px side padding, 44px minimum target, safe-area inset 적용.
- Studio sections는 route 또는 복원 가능한 step state로 표현한다.
- Inspector는 bottom sheet, summary는 accordion으로 바꾼다.
- Player는 mini-player로 축소하고 tap 시 full-screen player로 전환한다.
- keyboard가 열린 동안 primary action이 입력을 가리지 않게 한다.
- horizontal form grid를 사용하지 않고 label 위 control로 쌓는다.

## Component 변환표

| Desktop | Tablet | Mobile |
|---|---|---|
| Sidebar | Icon rail | Bottom navigation |
| Right inspector | Side drawer | Bottom sheet |
| 3-column Studio | 2-column Studio | Step screen |
| Full transport | Compact transport | Mini-player/full player |
| Track table | Compact list | Card list |
| Modal | Modal/Drawer | Full-screen sheet |

## 검증 Matrix

- 320, 360, 390, 768, 1024, 1280, 1440, 1920px에서 overflow 검사.
- Chrome, Safari, Edge와 iOS Safari, Android Chrome을 검토한다.
- portrait/landscape, text zoom 200%, reduced motion, high contrast를 포함한다.
- touch, keyboard, mouse, screen reader 기본 경로를 검증한다.
