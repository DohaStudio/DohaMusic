# 로컬 Dataset·Artifact 공통 관리 정책

> 문서 상태: [승인]
> 최종 수정일: 2026-08-05
> 관련 기능: DohaLM·DohaAudio·DohaVocal 로컬 데이터와 모델 산출물 관리
> 관련 문서: [Dataset 구조](dataset-structure.md), [Audio Data Policy](audio-data-policy.md), [Provider Model Manifest](../04-models/provider-model-manifest.md), [책임 경계](../03-architecture/repository-provider-boundaries.md)

## 원칙

Dataset과 Artifact는 Git 밖에서 관리한다. 저장소에는 재현과 검증에 필요한 schema·설정·계보 metadata만 포함한다. 코드, 문서와 manifest에 개발자 PC의 절대 경로를 하드코딩하지 않는다.

## 개발자 로컬 예시

```text
D:/DohaData/
├── lm/
├── music/
└── vocal/

D:/DohaArtifacts/
├── lm/
├── music/
└── vocal/
```

위 경로는 Windows 개발 환경 예시이며 표준 경로가 아니다. 실제 경로는 환경 변수로 주입한다.

```env
DOHA_DATA_ROOT=D:/DohaData
DOHA_ARTIFACT_ROOT=D:/DohaArtifacts

DOHALM_DATA_ROOT=D:/DohaData/lm
DOHAAUDIO_DATA_ROOT=D:/DohaData/music
DOHAVOCAL_DATA_ROOT=D:/DohaData/vocal
```

각 저장소는 공통 root가 없을 때 저장소별 root를 사용할 수 있다. 배포 환경과 CI는 Windows drive를 전제하지 않으며 secret·volume·object storage 설정으로 대체할 수 있어야 한다.

## 권장 논리 구조

```text
{provider-data-root}/
├── raw/
├── interim/
├── processed/
├── manifests/
├── splits/
├── runs/
└── cache/

{provider-artifact-root}/
├── checkpoints/
├── adapters/
├── evaluations/
├── exports/
└── manifests/
```

Manifest의 파일 참조는 해당 Dataset·Artifact root에 대한 상대 경로 또는 논리 ID로 기록한다. `D:/...`, 사용자 홈, checkout 경로를 저장하지 않는다.

## Git 포함 정책

Git에 포함할 수 있는 항목:

- Dataset schema와 Manifest schema
- 전처리 설정과 학습 설정 예제
- 데이터 출처·라이선스·허용 범위 metadata
- Checksum 목록
- 개인정보가 없고 재배포가 허용된 작은 테스트 fixture

Git에서 제외하는 항목:

- 원본·전처리 음원과 실제 가사 Dataset
- 개인 음성
- Checkpoint, Adapter와 모델 가중치
- 생성 음원과 Preview
- 학습 cache와 임시 실행 파일
- 개인정보와 동의 증적 원본

## 계보와 삭제

- Dataset version은 입력 sample, 전처리 version, split과 checksum을 추적한다.
- Training Run은 Dataset version과 생성한 Checkpoint·Adapter를 연결한다.
- Evaluation은 Model Manifest와 고정 평가 Dataset version을 연결한다.
- 음성 동의 철회와 삭제 결정은 DohaMusic이 소유하며 DohaVocal은 원본·전처리본·cache·Checkpoint·Adapter 파생 계보에 삭제 결과를 반환해야 한다.
- 개인 Vocal 영역은 다른 Dataset과 물리적·논리적으로 격리하고 최소 권한을 적용한다.

## 현재 상태

이 문서는 공통 정책만 정의한다. `DohaAudio`, `DohaVocal`, 공통 Artifact service, URI 기반 전달과 공통 Model Registry는 모두 `[계획]`이며 생성·구현된 것으로 간주하지 않는다.
