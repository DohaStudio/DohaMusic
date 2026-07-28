# 로컬 개발 환경

> 문서 목적: 향후 재현 가능한 로컬 개발 환경의 기준을 정의한다.
> 현재 상태: **Backend Foundation 실행 절차 완료**

현재 구성은 Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite, 프로세스 내부 Mock Worker와 로컬 Audio Storage다. Frontend, Redis와 실제 AI 모델은 포함하지 않는다.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic -c backend/alembic.ini upgrade head
python -m uvicorn backend.main:app --reload
```

검증 명령:

```powershell
python -m pytest -q
python -m compileall -q backend
python -m alembic -c backend/alembic.ini current
```

기본 SQLite와 생성 파일은 `backend/storage/` 아래 생성되며 Git에서 제외된다. API 문서는 `/docs`, health는 `/health`에서 확인한다. 모델 다운로드, GPU, Docker 실행은 Phase 1 범위에 없다.
