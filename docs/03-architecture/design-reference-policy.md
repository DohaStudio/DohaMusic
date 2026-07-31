# Frontend Design Reference Policy

> 문서 상태: [운영 기준]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 Doha Studio
> 관련 문서: [Frontend Overview](frontend-overview.md), [Design System](design-system.md), [UI Component Guide](ui-component-guide.md)

## 목적

첨부된 Vinyl Music Dashboard 이미지의 시각적 방향을 참고하면서 DohaMusic 고유 UI를 만들고 저작권·상표·자산 오용을 방지한다.

## 허용되는 참고 범위

- 좌측 Navigation, 중앙 Workspace, 우측 Context Panel, 하단 Player의 정보 배치 원리
- dark surface, warm beige와 red accent의 color 방향
- vinyl·turntable을 음악 제작 상태의 시각적 metaphor로 사용하는 아이디어
- rounded card, soft shadow, restrained glass와 넓은 여백
- Desktop dashboard와 Mobile step flow의 관계

## 금지 사항

- 원본 UI의 화면·간격·구성·microcopy를 그대로 복제하지 않는다.
- 원본 브랜드, logo, album, artist 이름과 trademark 요소를 사용하지 않는다.
- 레퍼런스 artwork·사진·icon을 DohaMusic 서비스·문서 asset으로 재사용하지 않는다.
- 출처·라이선스가 불명확한 이미지를 Production asset이나 학습 자료로 포함하지 않는다.
- 레퍼런스와 혼동될 정도로 고유 trade dress를 모방하지 않는다.

## DohaMusic 재해석 기준

- [Design System](design-system.md)의 DohaMusic token을 사용한다.
- 음악 감상 UI가 아니라 Settings → Lyrics → Voice → Review → Generation → Result 제작 흐름을 중심으로 재구성한다.
- vinyl motion은 생성·재생 상태를 설명하는 기능적 feedback이어야 하며 reduced motion을 지원한다.
- artwork는 권리 확인된 자체 asset, 사용자 생성 asset 또는 명확히 허용된 placeholder만 사용한다.

## 검토 체크리스트

- [ ] 원본 logo·artist·album·artwork가 포함되지 않았다.
- [ ] DohaMusic token·component로 재설계됐다.
- [ ] 사용 asset의 출처·라이선스·권리 상태가 기록됐다.
- [ ] 접근성·반응형 요구가 reference보다 우선 적용됐다.
- [ ] Production 포함 전 디자인·법률 검토 필요 여부를 확인했다.
