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

Key 없이 `template`·`mock`을 쓰면 애플리케이션은 정상 시작한다. `openai`를 명시 선택했는데 Key가 없으면 `LYRICS_API_KEY_MISSING` 설정 오류로 시작을 거부한다. 일반 테스트는 외부 호출이 없다. 유료 smoke test는 Key와 `DOHAMUSIC_RUN_PAID_LYRICS_TESTS=1`을 모두 설정하고 `pytest -m "external and paid"`로 명시 실행한다.

현재 호출 총 deadline은 5초 이하다. 더 긴 운영 요청은 AGENTS의 긴 작업 정책에 따라 동기 HTTP가 아닌 Job/Queue/Worker로 전환해야 한다.
