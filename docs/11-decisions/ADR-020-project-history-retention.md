# ADR-020: Project 삭제와 History 보존 정책

> 상태: **승인**
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 History·Project API

## 배경과 문제

Pipeline Job을 다시 찾고 재생·다운로드하려면 영속 History와 Project 분류가 필요하다. Project 삭제가 Job과 결과 파일까지 연쇄 삭제하면 사용자의 생성 결과를 복구하기 어렵다.

## 결정

Pipeline 생성 시 명시한 Project가 없으면 단일 `Default Project`를 재사용하거나 생성한다. History는 별도 복제 테이블이 아니라 `pipeline_jobs`와 Voice·File metadata의 안전한 공개 projection이다.

Project 삭제 시 연결 Job의 `project_id`만 `NULL`로 설정하고 Project row만 삭제한다. Pipeline Job, Pipeline File row와 Storage 결과 파일은 유지한다. 삭제된 기본 Project는 다음 Pipeline 생성 시 다시 만들어진다.

## 선택 이유와 영향

- 생성 결과의 우발적 손실을 방지한다.
- 기존 Pipeline 상태·파일 접근 계약을 재사용한다.
- Public DTO에는 Storage·절대 경로·filesystem·temp·Provider 설정을 포함하지 않는다.
- 인증·소유권이 없는 현재 단계는 로컬 단일 사용자 경계이며 공개 운영 승인이 아니다.

## 대안

- Project와 Job cascade 삭제: 복구가 어려워 제외했다.
- History 복제 테이블: 상태 불일치 위험이 있어 제외했다.
- Project 삭제 금지: 사용자의 정리 요구를 충족하지 못해 제외했다.

## 재검토 조건

- 인증·소유권 및 사용자별 Project 격리 도입
- 휴지통·보존 기간·영구 삭제 기능 도입
- Object Storage 또는 다중 사용자 운영 전환
