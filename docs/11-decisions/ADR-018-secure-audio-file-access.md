# ADR-018 — Secure Audio File Access

> 상태: 승인
> 작성일: 2026-07-31
> 최종 수정일: 2026-08-05
> 관련 기능: Phase 8 Doha Studio Audio Player·WAV Download
> 관련 문서: [Pipeline API](../06-api/pipeline-api.md), [Security Policy](../09-security/security-policy.md), [Frontend Architecture](../03-architecture/frontend-architecture.md)
> 관련 PR: [PR #21](https://github.com/DohaStudio/DohaMusic/pull/21)

## 배경

Pipeline은 생성 결과 경로를 내부 DB와 Storage에 보관하지만 공개 DTO는 경로를 의도적으로 숨긴다. Phase 8 Player와 WAV Download에는 브라우저가 Range 요청을 보낼 수 있는 안전한 파일 전달 경계가 필요하다.

## 문제

경로를 DTO에 노출하거나 정적 디렉터리를 공개하면 traversal, symlink, 임의 파일 접근과 소유권 우회 위험이 생긴다. 반대로 Backend가 전체 WAV를 메모리에 읽으면 큰 파일과 Range 재생에서 비효율적이다. 현재 인증·소유권이 없으므로 로컬 MVP와 공개 운영 조건도 구분해야 한다.

## 결정

1. 첫 범위는 완료된 Pipeline 결과의 허용된 WAV로 제한한다.
2. 공개 files DTO에는 opaque `job_id`·`file_id`, capability boolean과 상대 `content_url`·`download_url`만 제공하고 내부 경로는 제공하지 않는다.
3. 매 요청에 Job/File 존재와 소속, `COMPLETED`, 공개 file type, Storage root 내부 real path, symlink 부재, regular file, 1 GiB 이하 크기, `.wav`·허용 MIME·RIFF/WAVE header를 검증한다.
4. `GET|HEAD content`와 `GET|HEAD download`는 Starlette `FileResponse`로 stream한다. 단일 byte Range를 지원하고 무효·다중·범위 밖 요청은 안정적인 `416 INVALID_RANGE`로 거절한다.
5. content는 inline, download는 서버가 만든 ASCII `.wav` attachment filename을 사용한다. 모든 응답에 `Cache-Control: private, no-store`와 `X-Content-Type-Options: nosniff`를 적용한다.
6. Starlette가 생성하는 `ETag`·`Last-Modified`는 조건부 요청 식별자로 유지한다. `no-store`가 저장을 금지하므로 공유 cache를 신뢰 경계로 사용하지 않는다.
7. Frontend는 DTO capability URL만 신뢰하며 임의 외부 URL과 파일 경로를 media source로 사용하지 않는다. Player 상태는 메모리에만 유지한다.

## 선택 이유

기존 Pipeline Repository·Service와 Storage root를 재사용하면서 파일 권한 판단을 한 경계에 모을 수 있다. `FileResponse`는 전체 파일 메모리 적재 없이 표준 Range·HEAD 응답을 제공하고, same-origin Next.js rewrite를 통해 브라우저에 Backend 주소를 직접 노출하지 않는다.

## 대안

- 정적 Storage 공개: 구현은 단순하지만 Job/File 상태·소속 검증과 경로 은닉이 어려워 제외했다.
- Backend `read_bytes()` 응답: 작은 파일에는 단순하지만 대용량과 Range에서 메모리 비용이 커 제외했다.
- signed URL/object storage: 공개 운영에는 유효하지만 현재 로컬 filesystem과 인증 체계가 없어 후속 검토한다.
- Generation·Stem·Voice 각각 endpoint 추가: 중복 권한 경계가 생기므로 첫 범위에서 제외하고 Pipeline 결과부터 검증한다.

## 장점과 단점

장점은 경로 비노출, 일관된 오류, 브라우저 seek, stream 기반 메모리 사용, 기존 Adapter·Pipeline 비변경이다. 단점은 현재 WAV·단일 Range로 제한되고 filesystem 검증을 요청마다 수행하며, 인증 없는 URL 자체는 secret capability가 아니라는 점이다.

## 보안 및 운영 위험

로컬 단일 사용자에서는 opaque ID가 편의 경계일 뿐 인가 수단이 아니다. 공개 운영 전에 인증, 자원 소유권·인가, rate limit, 다운로드 감사 로그, 보존·삭제, 만료 URL 또는 동등한 접근 통제, reverse proxy의 Range·cache 정책, 대용량·동시 연결 제한을 구현하고 보안 검토해야 한다. 이 조건 전에는 Production Provider나 외부 공개 endpoint로 승격하지 않는다.

## 영향과 마이그레이션

기존 Pipeline 생성·AI Provider·Storage schema는 바꾸지 않는다. files public DTO에 nullable URL 필드가 추가되며 기존 client는 capability false/null을 계속 처리할 수 있다. 새로운 환경 변수와 의존성은 없다.

## 재검토 조건

- 인증·다중 사용자·소유권 모델 도입
- object storage·CDN·signed URL 도입
- WAV 외 format 또는 다중 Range 요구
- 1 GiB 제한과 동시 stream 운영 지표 변경
- Starlette `FileResponse` Range·보안 동작의 호환성 변경
