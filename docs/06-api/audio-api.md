# 오디오 API

> 문서 목적: 참조 음성 업로드와 생성 파일 접근 계약을 정의한다.
> 현재 상태: **설계 초안 / 미구현**

- `POST /api/v1/voice-samples`: 동의 정보와 음성 파일 업로드
- `POST /api/v1/voice-profiles`: 검증된 샘플로 프로필 생성
- `DELETE /api/v1/voice-profiles/{id}`: 사용 중지와 삭제 절차 시작
- `GET /api/v1/files/{file_id}`: 소유권 확인 후 다운로드 또는 스트리밍

서버는 확장자가 아닌 실제 디코딩 결과, MIME, 크기, 길이를 검증한다. 업로드와 다운로드 제한은 [파일 업로드 보안](../09-security/file-upload-security.md)을 따른다.
