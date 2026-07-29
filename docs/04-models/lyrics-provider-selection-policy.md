# Lyrics Provider 선정 및 수명주기 정책

## Provider Matrix

```text
template (Stable 기본값)
  → openai (Experimental, 명시적 선택)
  → template fallback (요청별 명시적 허용 시만)
  → mock (테스트 전용)
```

- `Experimental`: Adapter와 자동 테스트는 있으나 외부 실측·사용자 품질·법무·개인정보 승인이 끝나지 않음
- `Preview`: 제한된 사용자·비용 한도에서 실제 실측과 품질 평가 통과
- `Stable`: 한국어 품질, 수정 지시, 비용, 지연, 데이터 정책, 인증·소유권, 장애 대응 승인
- `Rejected`: 기술·비용·권리·보안 기준을 충족하지 못해 선택 불가

기본값은 `template`이며 OpenAI를 자동 선택하지 않는다. OpenAI 실패는 timeout, 일시적 network/5xx, rate limit에만 재시도한다. 인증·잘못된 요청·콘텐츠 차단·유효하지 않은 출력은 재시도하지 않는다. Template fallback은 `allow_template_fallback=true`일 때만 수행하고 실제 Provider와 사유를 metadata에 남긴다.

가격은 설정 한 곳과 비용 모듈에서만 계산한다. 가격·버전이 설정되지 않으면 `estimated_cost=null`이다. 요청 후 계산되는 비용 한도는 이미 발생한 청구를 예방하지 못하므로 운영 전 사전 token budget·계정 한도도 필요하다.

사용자 인증이 없어 `DOHAMUSIC_LYRICS_MAX_DAILY_REQUESTS` 같은 사용자별 일일 제한은 이번에 구현하지 않았다. 운영 전 인증 주체와 원자적 사용량 저장소를 먼저 설계한다.

승격 전에는 EVAL-006 사용자 평가, 실제 네 시나리오 benchmark, 법률 검토, 데이터 처리 승인, 사용자 인증·소유권, 비동기 Job·취소 정책이 필요하다.
