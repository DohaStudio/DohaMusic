# 로컬 개발 환경

> 문서 목적: 향후 재현 가능한 로컬 개발 환경의 기준을 정의한다.
> 현재 상태: **계획 / 설치 절차 미확정**

예상 구성은 Node.js 기반 Next.js, Python 기반 FastAPI·Worker, PostgreSQL, 선택적 Redis, 로컬 Audio Storage다. 정확한 버전과 설치 명령은 첫 구현 PR에서 lockfile·도구 설정과 함께 확정한다.

모델 다운로드·패키지 설치·Docker 실행은 이번 문서 작업 범위에 포함되지 않았다. GPU 검증 환경은 RTX 3060 Ti 8GB, 드라이버·CUDA·PyTorch 조합을 실험 보고서에 정확히 기록한다.
