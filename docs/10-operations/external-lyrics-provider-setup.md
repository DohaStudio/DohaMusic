# External Lyrics Provider 설정

기본 Provider는 계속 `template`다. 실제 비밀값은 `.env` 또는 배포 secret에만 둔다.

```dotenv
DOHAMUSIC_LYRICS_PROVIDER=openai
DOHAMUSIC_LYRICS_MODEL=gpt-5-mini-2025-08-07
DOHAMUSIC_LYRICS_API_KEY=
DOHAMUSIC_LYRICS_BASE_URL=https://api.openai.com/v1
DOHAMUSIC_LYRICS_TIMEOUT_SECONDS=2
DOHAMUSIC_LYRICS_TOTAL_DEADLINE_SECONDS=5
DOHAMUSIC_LYRICS_MAX_RETRIES=1
DOHAMUSIC_LYRICS_MAX_OUTPUT_TOKENS=2000
```

비용 metadata가 필요하면 조사일 가격과 버전을 운영자가 명시한다. 공식 가격이 바뀌면 함께 갱신한다.

```dotenv
DOHAMUSIC_LYRICS_INPUT_COST_PER_MILLION=0.25
DOHAMUSIC_LYRICS_OUTPUT_COST_PER_MILLION=2.0
DOHAMUSIC_LYRICS_PRICING_VERSION=2026-07-29
DOHAMUSIC_LYRICS_MAX_COST_PER_REQUEST=
```

Key 없이 `template`·`mock`을 쓰면 애플리케이션은 정상 시작한다. `openai`를 명시 선택했는데 Key가 없으면 `LYRICS_API_KEY_MISSING` 설정 오류로 시작을 거부한다. 일반 테스트와 CI는 실제 외부 API를 호출하지 않는다.

## 비용 발생 방지

- 무료 크레딧·무료 한도가 있어도 사용자 승인 없이 호출하지 않는다.
- 결제 수단 등록을 요청하거나 진행하지 않는다.
- 실제 Token 비용이 발생하는 benchmark와 유료 통합 테스트를 일반 검증에서 실행하지 않는다.
- 기본값 `DOHAMUSIC_LYRICS_PROVIDER=template`과 External Provider `Experimental` 상태를 유지한다.
- 실제 실측은 `[사용자 승인 필요]`, `[API Key 필요]`, `[유료 실측 미수행]` 상태다.

유료 smoke test는 사용자가 별도로 승인한 실행에서만 다음 세 조건을 모두 명시적으로 준비한다. 승인 전에는 아래 변수를 설정하지 않는다.

```dotenv
DOHAMUSIC_USER_APPROVED_PAID_LYRICS_TESTS=1
DOHAMUSIC_RUN_PAID_LYRICS_TESTS=1
DOHAMUSIC_LYRICS_API_KEY=<승인된 secret>
```

그 후에도 `pytest -m "external and integration and paid"`로 해당 테스트만 분리 실행한다. Marker가 없는 일반 테스트 또는 CI 명령에 위 변수를 주입하지 않는다.

현재 호출 총 deadline은 5초 이하다. 더 긴 운영 요청은 AGENTS의 긴 작업 정책에 따라 동기 HTTP가 아닌 Job/Queue/Worker로 전환해야 한다.
