# 로컬 Inter·Manrope 폰트

> 문서 상태: [진행 중 — production build 통과·시각 비교 미검증]
> 최종 수정일: 2026-10-12

빌드 중 Google Fonts 연결이 필수였던 `next/font/google`을 로컬 정적 자산으로 변경했다. 기존 폰트 family·variable weight·Unicode range·Arial fallback metrics·Latin preload를 유지한다. [fonts.css](../../styles/fonts.css)는 기존 Google Fonts 생성 CSS의 15개 font-face를 보존하고 URL만 로컬 경로로 바꾼다. 새 글꼴이나 font subset을 생성하지 않았다.

WOFF2는 원본 worktree의 `frontend/.next/static/media` cache에서 읽기 전용으로 복사했다. 원본 폴더에는 쓰지 않았다. Inter 7개·Manrope 6개 subset이며 번호는 원본 CSS 순서다. Latin preload는 `inter-7`, `manrope-6`다. 런타임에서는 `/fonts/*.woff2`와 [OFL.txt](OFL.txt)를 제공한다.

라이선스는 SIL OFL 1.1이다. 저작권 고지와 전체 라이선스를 함께 보존한다. 공식 출처: [Inter OFL](https://github.com/google/fonts/blob/main/ofl/inter/OFL.txt), [Manrope OFL](https://github.com/google/fonts/blob/main/ofl/manrope/OFL.txt).

| 파일 | 원본 cache 파일 | SHA256 |
|---|---|---|
| inter-1.woff2 | 2c55a0e60120577a-s.0-dom-5bn10r2.woff2 | fccca918fea40089dacadc7045861314d1a6bc91f1f323cc1eeb22ebcdb321b5 |
| inter-2.woff2 | 9c72aa0f40e4eef8-s.1y4-pdgsjb-pw.woff2 | aebf2ab4a4ce6810d73c1ac7be7cafb4e5ec4cee2d6db5fb3e09691747ec4bd6 |
| inter-3.woff2 | ad66f9afd8947f86-s.3lvt2whj97whp.woff2 | a2e2c783ca6f9c20486e81e72a279203e86730bbf8f01ff6a5ee9dbd09e1c271 |
| inter-4.woff2 | 5476f68d60460930-s.2uwcyprjm3xu3.woff2 | 46dd4cdca58c26ae87cc6927657bf83b2e8abfc39ffd0ab176e301a8d28d22bf |
| inter-5.woff2 | 2bbe8d2671613f1f-s.0k62hbripvv8p.woff2 | 8db00ff46c67b22cda8bed865acf7077651cac8d2841d5b40980556b48961931 |
| inter-6.woff2 | 1bffadaabf893a1e-s.3-6t-g6q0vh0a.woff2 | a28eb6d3ccb534ae0c94ca999371df024aab60b08c3c8a5720ee9e32fa0faaa2 |
| inter-7.woff2 | 83afe278b6a6bb3c-s.p.2bn3s6zvc0dyp.woff2 | c940764593d0fe5d596be327ca7558855e018039fb78509aa21921fd3644c3e4 |
| manrope-1.woff2 | a342834df7752944-s.3hd2l7bm32o7k.woff2 | e8c0b39992f06b3dc9a9834494088014859f363bf6ca8792b6bb07e17c7965f3 |
| manrope-2.woff2 | d3fe2f289711ac3f-s.1l2zhvq5eocqf.woff2 | 95a493061fe0a8d0d027c2892747134ba747141112d3be4d5022e70ab7d3a1a6 |
| manrope-3.woff2 | 58c4895d0a0ef7cc-s.2vhvl9vrvk-va.woff2 | 40af11327fe5308166c6cb5787808b042db6da889abf602f0a4876c49675d87e |
| manrope-4.woff2 | bfc7db5c00d21bc5-s.173xwsdme27n8.woff2 | bab757f8a0a1bc04055ee98cb5777f3254aab11f6d222366e1f40a36f390506a |
| manrope-5.woff2 | 6ab0db14f70d8ed6-s.13hnt-xgp82zk.woff2 | ce093b341d9c10658ee1eaa85c5f8042ff3307bc6ccfc5f405616eb437f0009e |
| manrope-6.woff2 | a343f882a40d2cc9-s.p.1sj6eobyi31rd.woff2 | e310b55a7fd9677f5e3555e6c6c4d064fa1f1d24393f0ddbe217cea12a8c432f |

바이너리 동일성·CSS descriptor 일치는 확인했다. 실제 브라우저 screenshot 비교는 아직 검증하지 않았다. 결과는 [EVAL-008](../../../reports/evaluations/EVAL-008-audio-analysis-validation.md)에 기록한다.
