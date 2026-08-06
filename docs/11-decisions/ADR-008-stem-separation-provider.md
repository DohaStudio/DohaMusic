# ADR-008: HTDemucs Stem Provider와 출력 계약

> 상태: **채택됨**
> 결정일: 2026-07-29
> 관련 작업: Phase 3 Stem Separation

## 배경

생성 음악에서 보컬을 분리해 다음 Phase의 Seed-VC 입력으로 전달해야 한다. Backend는 모델 라이브러리, 4-stem 세부 구조와 GPU 환경에 직접 의존하지 않아야 하며 모델 없는 개발 환경도 동작해야 한다.

## 결정

1. 공통 경계는 `StemSeparator`로 정의하고 기본 Provider는 `mock`으로 유지한다.
2. 실제 선택 Provider는 Demucs 4.1.0의 기본 `htdemucs`다.
3. Adapter는 공식 4-stem 출력 중 `vocals`를 보컬로 사용하고 나머지를 합산해 `instrumental`을 만든다.
4. 외부 계약은 48kHz, Stereo, IEEE float32 WAV 두 파일과 JSON metadata다.
5. Demucs는 별도 Python 환경의 Job별 subprocess에서 오프라인 실행한다. 모델은 자동 다운로드하지 않는다.
6. 생성과 Stem Worker는 GPU 동시성 1인 공유 executor를 사용한다.
7. Stem은 별도 `stem_jobs`로 추적하고 원본 `generated_files`를 외래키로 참조한다.

## 근거

공식 문서상 HTDemucs가 기본 모델이고 CUDA, 2-stem vocals, segment 옵션을 지원한다. RTX 3060 Ti에서 20초 입력 3/3 성공, 순수 분리 평균 3.915초, 시스템 GPU 메모리 피크 평균 2,555.67MiB였다. 코드와 사용 가중치의 공식 표시는 MIT다. 자세한 수치는 [EXP-003](../../reports/experiments/EXP-003-stem-separation.md)에 있다.

## 대안

- `htdemucs_ft`: 품질 가능성은 있으나 공식 설명상 약 4배 느려 초기 기본값에서 제외했다.
- MDX-Net: 공식 challenge 성과가 있으나 현재 유지보수와 Backend 패키징 경계를 추가 검증해야 한다.
- Open-Unmix: 구조와 MIT 코드가 명확하지만 공식 비교 성능이 HTDemucs보다 낮아 우선순위에서 제외했다.
- 같은 generation Job에 상태만 추가: 산출물 재처리와 오류 추적이 결합되어 별도 `stem_jobs`보다 책임이 불명확하다.

## 영향과 재검토

장점은 모델 교체 경계, 개발용 Mock, 명시적 자원·오류 격리와 Seed-VC 입력 형식 고정이다. 단점은 subprocess load 비용, 두 개 Job 조회, 로컬 ThreadPool의 비내구성이다.

EVAL-002에서 보컬 손실·누출이 허용되지 않거나 다른 모델이 동일 환경에서 명확히 우수하면 Provider를 재검토한다. 출력 형식, 외래키 또는 동시성 정책을 바꿀 때는 대체 ADR과 migration을 작성한다. 수동 평가 전에는 청감 품질을 승인하지 않는다.
