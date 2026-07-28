# Backend 아키텍처

> 문서 목적: FastAPI Backend Foundation의 계층과 책임을 정의한다.
> 현재 상태: **Phase 1 구현 완료**

```text
backend/
├── alembic/       # DB 마이그레이션
├── ai/             # 생성 인터페이스, Adapter 경계, Mock 구현
├── api/            # Router, Dependency, 예외 응답
├── app/            # 애플리케이션 팩토리와 lifespan
├── core/           # 환경 설정, 로깅, 오류, 상태 전이
├── db/             # SQLAlchemy Base/Session, Alembic 실행
├── models/         # ORM 모델
├── repositories/   # 영속성 접근
├── schemas/        # 요청·응답 계약
├── services/       # 유스케이스 조정
├── storage/        # 로컬 저장소와 샘플 관리
├── tests/          # API·DB·Worker 테스트
├── workers/        # Dispatcher와 Mock Worker
└── main.py         # ASGI 진입점
```

의존 방향은 `API → Service → Repository → Model`이다. Worker도 Repository와 `MusicGenerator` 인터페이스를 사용하며 특정 AI 라이브러리를 직접 참조하지 않는다. FastAPI Dependency는 앱 lifespan에서 구성된 서비스를 Router에 제공한다.

애플리케이션 시작 시 저장소 디렉터리를 준비하고 Alembic을 `head`까지 적용한 뒤 Repository, Service, Mock Worker를 조립한다. 공개 오류는 공통 `{ "error": { "code", "message" } }` 형식으로 변환하며 내부 예외 정보는 로그에만 남긴다.

설정은 환경 변수로 덮어쓸 수 있다. 세부 항목은 [환경 변수](../10-operations/environment-variables.md), API 계약은 [API 개요](../06-api/api-overview.md)를 따른다.
