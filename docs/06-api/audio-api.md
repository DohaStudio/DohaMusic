# 음성 프로필 API

> 문서 목적: Phase 1 음성 프로필 메타데이터 API를 정의한다.
> 현재 상태: **메타데이터 생성·삭제 구현 완료**

## 프로필 생성

`POST /api/voice-profiles`

```json
{
  "name": "내 음성",
  "reference_file_path": "voices/reference.wav",
  "consent_confirmed": true
}
```

`name`은 1~100자, `reference_file_path`는 1~500자다. `consent_confirmed`는 반드시 `true`여야 하며 성공 시 `201`과 프로필 메타데이터를 반환한다.

## 프로필 삭제

`DELETE /api/voice-profiles/{id}`

성공 시 본문 없는 `204`를 반환한다. 존재하지 않는 ID는 `404 RESOURCE_NOT_FOUND`다.

Phase 1은 실제 음성 파일 업로드, 디코딩·MIME 검증, 음색 변환, 사용자 소유권 검사를 구현하지 않는다. `reference_file_path`는 참조 메타데이터이며 서버가 해당 파일을 읽거나 처리하지 않는다.
