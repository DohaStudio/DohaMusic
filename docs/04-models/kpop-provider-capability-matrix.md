# K-POP Provider Capability Matrix

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 기능: K-POP Generation Capability
> 관련 문서: [Generation Options](../03-architecture/kpop-generation-options.md), [EVAL-007](../../reports/evaluations/EVAL-007-kpop-dance-generation.md)

상태는 `지원`, `부분 지원`, `Prompt 기반`, `미검증`, `미지원`으로 구분한다. Prompt를 받아들인다는 사실을 세부 제어 지원으로 과장하지 않는다.

| Capability | mock | ACE-Step no LM | ACE-Step 0.6B LM | 향후 Provider |
|---|---|---|---|---|
| Prompt | 지원(테스트용) | 지원 | 지원 | 미검증 |
| Lyrics | 지원(테스트용) | 부분 지원 | 부분 지원 | 미검증 |
| Genre | Prompt 기반 | Prompt 기반 | Prompt 기반 | 미검증 |
| Duration | 지원 | 지원 | 지원 | 미검증 |
| Seed | 지원 | 지원 | 지원 | 미검증 |
| Requested BPM | 미지원 | Prompt 기반·미검증 | Prompt 기반·미검증 | 미검증 |
| Korean pronunciation | 미지원 | 미검증 | 미검증 | 미검증 |
| Section tags | 메타데이터 수준 | 부분 지원·미검증 | 부분 지원·미검증 | 미검증 |
| Hook | 미지원 | Prompt 기반·미검증 | Prompt 기반·미검증 | 미검증 |
| Post-Chorus | 미지원 | Prompt 기반·미검증 | Prompt 기반·미검증 | 미검증 |
| Dance Break | 미지원 | 미검증 | 미검증 | 미검증 |
| Long-form | 미지원 | 미검증 | 미검증 | 미검증 |
| Determinism | 테스트 재현 | 고정 환경 PCM 재현 확인 | 단일 표본·미검증 | 미검증 |
| Voice Conversion 입력 적합성 | 테스트용 | 미검증 | 미검증 | 미검증 |

ACE-Step 0.6B LM은 실행 가능성만 확인됐으며 단일 표본에서 no-LM 대비 품질 우위를 입증하지 않았다. 기본 Provider는 계속 `mock`, 운영 Provider는 미확정이다.

## Capability 기반 UI 초안

```json
{
  "kpop_generation": {
    "presets": true,
    "requested_bpm": "prompt_compiled",
    "language_ratio": "prompt_compiled",
    "hook_phrase": "prompt_compiled",
    "post_chorus": "prompt_compiled",
    "dance_break": "not_supported",
    "detected_bpm": "not_supported",
    "hook_preview": "not_supported"
  }
}
```

이는 설계 계약이며 이번 작업에서 API를 구현하지 않는다. Frontend는 향후 capability 응답이 구현되기 전까지 미지원 옵션을 활성화하지 않는다.
