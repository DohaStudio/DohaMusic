# UI Component Guide

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 설계 방식: Atomic Design
> 관련 문서: [Design System](design-system.md), [Page Structure](page-structure.md)

## Atoms

`Button`, `IconButton`, `Text`, `Heading`, `Label`, `Input`, `Textarea`, `Select`, `Checkbox`, `Radio`, `Switch`, `Slider`, `Badge`, `Chip`, `Divider`, `Spinner`, `Skeleton`, `Artwork`, `Icon`, `FocusRing`.

각 Atom은 default·hover·focus-visible·pressed·disabled·loading·error 중 적용 가능한 상태를 문서화하고 label·description·error 연결을 제공한다.

## Molecules

| Component | 구성 | 책임 |
|---|---|---|
| `FormField` | Label + control + help/error | 입력 접근성·검증 표시 |
| `TrackRow` | index + artwork + title + duration + action | 곡/결과 목록 표현 |
| `StepItem` | number + label + status | 현재·완료·대기·오류 단계 |
| `MetricRow` | label + value + unit | sample rate·peak·provider 등 |
| `VoiceProfileCard` | profile + consent + preview state | 음성 선택; audio 없으면 preview disabled |
| `InlineAlert` | icon + message + action | 오류·경고·복구 |
| `WaveformScrubber` | waveform + position + duration | 실제 URL 확보 후 seek |
| `ProviderBadge` | provider + lifecycle | Experimental·Mock 등 사실 표시 |

## Organisms

- `AppSidebar`: Desktop primary navigation, profile/plan 영역은 인증 전 placeholder로 만들지 않는다.
- `MobileBottomNav`: Studio·Lyrics·Voice·Projects·Settings. Projects는 API 부재 시 disabled/preview 표기한다.
- `StudioWorkspace`: 현재 section, canvas와 contextual action을 조합한다.
- `InspectorPanel`: settings summary, metadata, warnings, next action.
- `TransportBar`: player + waveform + queue; audio endpoint 전 disabled 상태.
- `StudioTimeline`: Settings → Lyrics → Voice → Review → Generation → Result.
- `LyricsEditor`: structured sections, validation warning, generate/revise action.
- `GenerationStatus`: current step, progress, elapsed, safe error, polling state.
- `ResultInspector`: artwork, quality metadata, files metadata, model/seed.
- `Modal`, `Drawer`, `ToastViewport`: overlay 계층과 focus management 담당.

## Templates

- `MarketingTemplate`: Landing/About, top navigation, immersive hero.
- `StudioTemplate`: Desktop 3-column + bottom transport.
- `FocusTemplate`: Lyrics/Voice 편집의 2-column workspace.
- `ProgressTemplate`: 생성 상태 중심, navigation 최소화.
- `ResultTemplate`: artwork/player 영역 + metadata inspector.
- `UtilityTemplate`: Settings/404.

## Pages

Landing, Studio, Lyrics Lab, Voice, Generation Progress, Result, Settings, About, 404가 template과 feature를 조합한다. 페이지는 API 호출 세부를 직접 소유하지 않는다.

## Component 계약 예시

문서 수준의 계약이며 코드가 아니다.

| Component | Input | Event | Empty/Error |
|---|---|---|---|
| StudioTimeline | sections, active, validity | section select | invalid section 설명 |
| GenerationStatus | job view model, connection | reconnect, start-over | Job 실패와 network 실패 분리 |
| LyricsEditor | draft, validation, mode | change, validate, generate, revise | revision 미지원 Provider 안내 |
| Player | media source, metadata | play, pause, seek | source endpoint 부재 상태 |
| VoiceProfilePicker | available session profiles | select, create, delete | list API 없음 안내 |

## 접근성 체크

- Dialog와 Drawer는 focus trap, close button, Escape와 focus return을 지원한다.
- Toast만으로 오류를 전달하지 않는다.
- color만으로 selected/progress/error를 구분하지 않는다.
- waveform과 artwork에 동등한 텍스트 정보가 있어야 한다.
- drag 동작에는 keyboard/button 대안을 제공한다.
