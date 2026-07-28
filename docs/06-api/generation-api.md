# 생성 API

> 문서 목적: 음악 생성 요청의 입력, 검증, 응답 계약을 정의한다.
> 현재 상태: **설계 초안 / 미구현**

`POST /api/v1/generation-requests`

요청 후보 필드: `prompt`, `lyrics`, `genre`, `mood`, `bpm`, `duration_seconds`, `seed`, `voice_profile_id`, `output_formats`. 프롬프트 또는 가사 중 하나 이상이 필요하며 음성 프로필은 유효한 동의와 소유권이 필요하다.

성공 시 `202`와 `generation_request_id`, `job_id`, `status=PENDING`을 반환한다. 같은 멱등성 키의 재전송은 동일 요청을 반환한다. 범위·형식 오류, 동의 오류, 모델 비가용 오류는 [오류 코드](error-codes.md)로 구분한다.
