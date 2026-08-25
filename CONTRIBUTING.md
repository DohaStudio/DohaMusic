# 기여 가이드

> 문서 목적: 문서와 향후 코드 변경의 품질·안전 기준을 정의한다.
> 현재 상태: **초안**

## 기본 원칙

1. 구현된 기능과 계획된 기능을 `[완료]`, `[진행 중]`, `[계획]`, `[검증 필요]`로 구분한다.
2. 모델 성능, VRAM, 언어 지원, 라이선스를 근거 없이 확정하지 않는다.
3. 음성 샘플·비밀 값·대형 모델 파일·생성 음원을 Git에 커밋하지 않는다.
4. 주제의 기준 문서를 수정하고 관련 문서에는 상대 링크를 둔다.

## 변경 절차

1. 관련 요구사항과 ADR을 확인한다.
2. 문서의 목적·현재 상태·관련 링크를 갱신한다.
3. Markdown 링크, Mermaid, 중복·모순을 확인한다.
4. 모델 실험은 [실험 보고서 템플릿](reports/experiment-report-template.md)으로 기록한다.
5. 아키텍처 결정 변경은 새 ADR을 작성하고 기존 ADR 상태를 대체됨으로 표시한다.

## Python 검증 기준

Tracked first-party Python root는 `backend`와 `ai_worker`이고 test root는
`backend/tests`다. 존재하지 않는 `src tests` 경로 또는 변경 파일만을 대상으로 삼지
않으며, 로컬과 CI에서 다음 명령을 동일하게 실행한다.

```powershell
python -m compileall -q backend ai_worker
python -m ruff check --no-cache backend ai_worker
python -m ruff format --check --no-cache backend ai_worker
python -m pytest -q
git diff --check
```

Ruff 예외는 `pyproject.toml`에 파일과 사유를 좁게 기록한다. `--unsafe-fixes`, 광범위한
ignore, 대량 `noqa`, `continue-on-error`로 Gate를 우회하지 않는다.

커밋 메시지는 한국어 또는 명확한 Conventional Commit 형식을 사용한다.
