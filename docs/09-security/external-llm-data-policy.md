# 외부 Lyrics LLM 데이터 정책

## 최소 전송

전송 허용 범위는 topic, genre, mood, keywords, language, section 구조, target duration, 추가 지시, 수정 시 원문 가사와 수정 지시뿐이다. 내부 DB ID, 파일 경로, API Key, Voice Profile, 음성 파일, 내부 로그와 불필요한 개인정보는 Prompt에 넣지 않는다.

API Key는 `DOHAMUSIC_LYRICS_API_KEY` 환경 변수에서만 읽으며 로그·DB·보고서에 저장하지 않는다. Provider 응답 header, 내부 request ID와 원문 오류 body를 사용자에게 노출하지 않는다. 요청 payload는 `store=false`를 지정한다.

OpenAI 공식 문서상 API 데이터는 기본적으로 모델 학습에 사용되지 않지만 abuse monitoring log는 기본 최대 30일 보존될 수 있고 ZDR/MAM은 승인형 통제다. 따라서 현재 Adapter는 개인정보·미공개 민감 가사 전송이 승인된 운영 채널이 아니다. 지역 저장, ZDR, DPA, 서비스 약관과 생성물 권리는 운영 전 법률·보안 검토가 필요하다.

수정 문서는 원본을 덮어쓰지 않는다. 로컬 DB에 parent/version, 수정 지시, 전후 SHA-256을 보존한다. 수정 이력이 있는 원본은 자식 버전이 남아 있는 동안 삭제를 거부한다. 인증·소유권과 보존기간은 아직 미구현이므로 운영 배포는 금지한다.
