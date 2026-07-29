# 데이터베이스 개요

> 문서 목적: 현재 영속 계층과 교체 경계를 정의한다.
> 현재 상태: **SQLite/SQLAlchemy/Alembic 구현 완료**

현재 기본 DB는 `backend/storage/doha_music.db`의 SQLite다. 연결 문자열은 `DATABASE_URL` 환경 변수로 변경할 수 있으며 Repository Pattern을 통해 Service와 Worker가 특정 DB 구현에 직접 의존하지 않도록 구성했다.

SQLAlchemy 2.x ORM을 사용하고 Alembic이 스키마 버전을 관리한다. 애플리케이션 시작 시 `head`까지 마이그레이션하며, 수동 실행은 다음 명령을 사용한다.

```bash
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini current
```

현재 테이블은 `generation_jobs`, `generated_files`, `voice_profiles`, `stem_jobs`, `stem_files`, `voice_conversion_jobs`, `voice_conversion_files` 일곱 개다. Stem Job은 입력 generated file을, Voice Conversion Job은 vocals Stem과 동의된 Voice Profile을 참조하고 결과 파일을 별도 추적한다. PostgreSQL 또는 MySQL 전환은 실제 운영 요구를 확인한 뒤 별도 검증하며, 현재 스키마에는 벤더 전용 타입이나 SQL을 사용하지 않는다.
