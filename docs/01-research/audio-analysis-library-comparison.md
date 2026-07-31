# Audio Analysis 라이브러리 후보 비교

> 문서 상태: [검토 완료·채택 전]
> 최종 수정일: 2026-07-31
> 관련 기능: K3 Audio Analysis 기술 후보
> 관련 문서: [K3 제품 정의](../02-product/k3-audio-analysis-product-definition.md), [EVAL-008](../../reports/evaluations/EVAL-008-audio-analysis-validation.md), [ADR-023](../11-decisions/ADR-023-audio-analysis-and-preview-architecture.md)

## 조사 원칙과 현재 환경

공식 문서·공식 저장소의 2026-07-31 확인 결과를 기록한다. 설치·실측은 수행하지 않았으며 버전·Windows wheel·Python 지원은 K3 구현 PR에서 다시 고정한다. 현재 Backend에는 NumPy와 SciPy만 직접 의존성으로 존재한다.

## 후보 비교

| 후보 | 라이선스·유지보수 확인 | Windows·설치 | 강점 | 한계와 판정 |
|---|---|---|---|---|
| [NumPy](https://numpy.org/doc/stable/license.html) | BSD 계열, 공식 저장소 활동 확인 | 공식 wheel, 이미 사용 | sample 연산, peak·clipping 기초 | BPM·LUFS·True Peak 완성 구현 아님. **기반 유지** |
| [SciPy](https://scipy.org/) | BSD-3-Clause, 공식 저장소 활동 확인 | Windows wheel, 이미 사용 | signal, resampling, filter primitives | 표준 loudness·tempo 제품 계약은 별도 구현 필요. **기반 유지** |
| [python-soundfile](https://python-soundfile.readthedocs.io/) | BSD-3-Clause, libsndfile 기반 | PyPI wheel이 Windows 포함 libsndfile 제공 여부 재검증 | WAV metadata·sample format 보존 I/O | Decoder 경계와 libsndfile 고지 필요. **K3.1 우선 평가** |
| [pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) | MIT, ITU-R BS.1770-4 구현, 2026-01 release 확인 | pure Python + NumPy/SciPy 후보 | Integrated LUFS, Loudness Range 후보 | 현재 ITU-R BS.1770-5·EBU test set과 오차 검증 필요, True Peak 제공 여부 별도. **K3.1 우선 평가** |
| [librosa](https://librosa.org/doc/latest/index.html) | ISC, 0.11 공식 문서와 저장소 활동 확인 | PyPI, 의존성 규모 중간 | onset·beat·tempo·tempogram, segmentation primitives | BPM은 추정이며 confidence API를 직접 설계·calibrate해야 함. **K3.2 우선 평가** |
| [FFmpeg](https://ffmpeg.org/documentation.html) | 기본 LGPL-2.1+, build 옵션에 따라 GPL; [법적 고지](https://ffmpeg.org/legal.html) 확인 필요 | 공식 프로젝트는 source 제공, Windows build는 연결된 제3자 배포 | decode/export, ebur128/loudnorm 기반 reference 후보 | 외부 실행·binary 배포·라이선스·command 보안 부담. **reference/후속 후보** |
| [Essentia](https://github.com/MTG/essentia) | AGPL-3.0, 공식 저장소 활동 확인 | C++/Python, Windows binding·배포 검증 필요 | 광범위한 rhythm·structure·descriptor | AGPL 및 설치·배포 크기 부담. **MVP 비채택** |
| [aubio](https://aubio.org/manual/latest/) | GPL-3.0, onset·beat·tempo 제공 | native build/Windows wheel과 Python 3.11+ 재검증 | 가벼운 onset·beat tracking | GPL 배포 영향과 confidence calibration 필요. **MVP 비채택** |
| [madmom](https://github.com/CPJKU/madmom) | source BSD, model/data CC BY-NC-SA 4.0; 최신 release는 오래됨 | Cython·FFmpeg·모델 의존, 최신 Python/Windows 검증 필요 | beat/downbeat/tempo와 MIR model | 비상업 모델 조건과 유지보수·호환성 위험. **제품 MVP 비채택** |

공식 저장소의 최근 commit은 안정 release나 DohaMusic 호환을 보장하지 않는다. 의존성을 추가할 때는 고정 version, transitive license, wheel provenance, 공급망·CVE를 별도 검토한다.

## 지표별 후보

| 영역 | 1차 후보 | reference 후보 | 검증 조건 |
|---|---|---|---|
| WAV decode·metadata | SoundFile 또는 현행 SciPy WAV | `wave`, ffprobe | PCM format·mono/stereo·sample rate·invalid file |
| Sample Peak·clipping | NumPy | reference fixture | dBFS 정의, integer scaling, non-finite 처리 |
| Integrated LUFS | pyloudnorm | EBU test set, FFmpeg ebur128/loudnorm | ITU-R BS.1770/EBU R 128 허용 오차 |
| True Peak | 미선정 | ITU-R BS.1770-5 호환 meter/FFmpeg 후보 | oversampling filter·dBTP reference 통과 전 미지원 |
| Tempo | librosa | 합성 ground truth·보조 analyzer | half/double, 무박 intro, tempo change, confidence calibration |
| Hook 후보 | NumPy/SciPy/librosa primitives | 사용자 label | 반복·energy score와 temporal overlap·유용성 |
| Preview export | SoundFile/SciPy 후보 | 현행 RIFF/WAVE 검사 | 정확한 길이, fade, 원본 비변경, secure access |

## LUFS와 True Peak 표준

- [ITU-R BS.1770-5](https://www.itu.int/rec/R-REC-BS.1770-5-202311-I)는 audio programme loudness와 true-peak 측정 알고리즘의 현재 기준이다.
- [EBU R 128](https://tech.ebu.ch/loudness/)은 BS.1770을 바탕으로 Programme Loudness, Momentary(400 ms), Short-term(3 s), Integrated, Loudness Range와 Maximum True Peak 사용 지침을 제공한다.
- K3.1은 Integrated LUFS를 우선하며 Short-term·Momentary·LRA는 후속이다.
- Sample Peak는 discrete sample 최댓값이다. True Peak는 inter-sample peak를 추정하는 표준 호환 oversampling이 필요하며 단순 Sample Peak를 dBTP라고 기록하지 않는다.

## 구현 전 Gate

1. Python 3.11+와 Windows 설치·wheel을 깨끗한 환경에서 재현한다.
2. 라이선스·transitive dependency·배포 고지와 상업 이용 가능성을 승인한다.
3. EVAL-008 reference fixture와 성능 예산을 통과한다.
4. analyzer output·confidence·version 계약을 고정한다.
5. 실패·취소·secure file access와 cleanup을 검증한다.

이번 문서 작업에서는 패키지를 설치하거나 코드를 실행하지 않았다.
