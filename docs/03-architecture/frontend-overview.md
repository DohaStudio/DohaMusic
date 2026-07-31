# Doha Studio Frontend Overview

> 문서 상태: [진행 중]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 Doha Studio
> 디자인 기준: 첨부된 Vinyl Music Dashboard 레퍼런스
> 관련 문서: [Frontend Architecture](frontend-architecture.md), [Studio UX Flow](studio-ux-flow.md), [Page Structure](page-structure.md), [지원 범위](#frontend-지원-범위), [디자인 레퍼런스 정책](design-reference-policy.md)

## 제품 경험

Doha Studio는 CRUD 폼이 아니라 “음악을 만드는 공간”이다. 사용자는 AI 기능을 호출한다기보다 작업대에서 곡 설정, 가사, 목소리와 결과를 다듬는 경험을 해야 한다.

기본 화면은 일반 사용자의 창작 언어를 우선한다. `Provider`, `Pipeline`, `Polling`, 내부 API 주소와 단계 식별자는 노출하지 않으며 `NEXT_PUBLIC_ENABLE_DEVELOPER_INFO=true`일 때만 설정의 접힌 개발자 정보에서 확인한다. 첫 방문 안내는 브라우저 로컬 상태에 완료 여부만 저장하고 설정에서 다시 열 수 있다.

음악 만들기의 기본 순서는 `음악 스타일 → 가사 → 내 목소리 → 최종 확인 → 음악 만드는 중 → 완성`이다. 장르 카드, 최대 3개 분위기, 30초·60초 길이 선택을 우선 제공하고 긴 곡과 세부 BPM은 실제 지원 전까지 비활성 상태와 이유를 함께 표시한다.

핵심 인상은 `Luxury · Premium · Dark · Minimal · Vinyl · Modern Dashboard · Glass · Soft Shadow · Rounded Card`다. Apple Music의 정제된 motion과 Spotify의 익숙한 탐색성을 참고하되 브랜드·UI를 복제하지 않고 DohaMusic의 제작 Workflow에 맞춘다.

## 레퍼런스 해석

- 좌측 rail: Studio, Lyrics Lab, Voice, Projects, Settings를 지속적으로 탐색한다.
- 중앙 작업대: 대형 vinyl/album artwork를 상태의 시각적 중심으로 사용한다.
- 우측 inspector: 현재 곡 정보, 생성 설정, metadata와 다음 행동을 배치한다.
- 하단 transport: Player, waveform, progress와 현재 Job timeline을 고정한다.
- 모바일: 한 화면 한 결정 원칙으로 설정 → 가사 → 목소리 → 확인 → 진행 → 결과를 이동한다.

Desktop의 대형 vinyl은 장식만이 아니라 상태 feedback이다. 준비 중에는 정지, 생성 중에는 저속 회전과 subtle pulse, 완료 시에는 검증된 Pipeline WAV를 전역 Player에서 재생한다. Player 상태는 메모리에만 두며 Backend 내부 경로나 media blob을 저장하지 않는다.

## 정보 구조

```text
Landing
└─ Studio Shell
   ├─ Studio Workspace
   │  ├─ Music Settings
   │  ├─ Lyrics
   │  ├─ Voice
   │  ├─ Review
   │  ├─ Generation
   │  └─ Result
   ├─ Lyrics Lab
   ├─ Voice
   ├─ Projects [Backend 선행 필요]
   ├─ Settings
   └─ About
```

Studio는 단순 6 Step Wizard가 아니다. Desktop에서는 workspace 안의 sections와 timeline으로, Mobile에서는 step navigation으로 같은 상태를 표현한다.

## 핵심 원칙

1. 음악 콘텐츠가 UI chrome보다 먼저 보인다.
2. 한 화면에는 하나의 primary action만 둔다.
3. 생성 상태는 percentage뿐 아니라 현재 음악 제작 단계와 다음 예상 상태로 설명한다.
4. 기술 Provider 이름은 개발자 정보 플래그에서만 제공하고 기본 흐름에서는 창작 언어를 사용한다.
5. 미구현 Backend 기능은 disabled action과 선행 조건으로 표시하며 가짜 결과를 만들지 않는다.
6. Desktop, Tablet, Mobile은 동일한 정보 우선순위를 다른 공간 구조로 표현한다.

## 페이지 역할

| 페이지 | 사용자 목표 | 현재 Backend 기준 |
|---|---|---|
| Landing | Studio 가치 이해·진입 | 정적 가능 |
| Studio | 곡 draft 구성·Pipeline 시작 | 가능 |
| Lyrics Lab | 생성·검증·조회·revision | 가능, provider 제약 표시 |
| Voice | 동의된 WAV upload·Profile list/get/delete·Studio 선택 | 로컬 MVP 가능, 원본 content 비공개 |
| Generation Progress | Pipeline 상태 추적 | 가능 |
| Result | 결과 metadata·품질 확인 | 가능, 재생/download는 endpoint 필요 |
| Settings | 로컬 UI 설정·Backend health | 부분 가능 |
| About | 프로젝트·권리·AI 사용 고지 | 정적 가능 |
| 404 | 안전한 복귀 | 정적 가능 |

## Frontend 지원 범위

| 상태 | 범위 |
|---|---|
| `Available` | Health, Lyrics, Voice Profile WAV upload·list·get·delete·선택, Pipeline Job·Cancel·Retry, History·Project, 결과 WAV 재생·download |
| `Partial` | Voice 원본 content 비공개, 개발 플래그에서만 서버 경로 생성, 인증 없는 로컬 단일 사용자 범위 |
| `Backend Required` | 인증·사용자 소유권, 모델 목록, 즐겨찾기·playlist |
| `Planned` | iOS·Android native app, PWA offline, 협업, 공유 링크, 공개 gallery, 결제·credit |

이 네 상태명을 관련 Frontend 문서와 UI specification에서 동일하게 사용한다. `Backend Required` 기능은 disabled 또는 “준비 중”으로만 표현하고 request를 보내지 않는다.

Files API의 HTTP response와 Frontend DTO 모두 `file_path`를 포함하지 않는다. Voice Profile response도 `reference_file_path`를 반환하지 않는다. 내부 DB와 Repository만 경로를 보유하며 UI는 `content_available`, `download_available`과 공개 metadata만 사용한다.

## Lyrics Provider 중립성

Frontend는 `template`, `openai`, 향후 `local_llm`의 SDK·Tokenizer·LoRA Adapter·GPU·추론 엔진을 직접 호출하거나 알지 않는다. `/api/lyrics`, Lyrics Revision·Validate 계약만 사용하며 Provider 결정은 Backend 설정과 운영 승인 정책을 따른다. 일반 사용자에게 Experimental Provider 선택 UI를 기본 제공하지 않고 Provider·모델은 결과 metadata로만 표시할 수 있다. Base Model이나 LoRA Adapter 교체는 Frontend 요청 계약을 변경하지 않으며, 미승인 Local Lyrics LLM을 “자체 AI 완료”로 표시하지 않는다.

## 성공 지표

- 첫 Studio 진입 후 사용자가 현재 작업과 다음 행동을 5초 안에 설명할 수 있다.
- Mobile 360px에서 horizontal overflow 없이 핵심 흐름을 완료한다.
- Job 새로고침 복원과 네트워크 오류/Job 실패를 구분한다.
- WCAG AA 대비, keyboard flow, reduced motion을 검증한다.
- API에 없는 기능을 성공 상태로 표시하는 화면이 0건이다.
