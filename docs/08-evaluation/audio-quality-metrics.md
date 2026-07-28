# 오디오 품질 지표

> 문서 목적: 자동 검사와 청취 평가 항목을 정의한다.
> 현재 상태: **Stem 기본 자동 검사 구현 / 청취 평가 대기**

자동 검사 후보는 파일 디코딩, 길이, 샘플레이트, 피크·클리핑, 무음 비율, loudness, 분리 누출 지표다. 단일 자동 지표로 음악 품질을 확정하지 않는다.

EXP-003 실행기는 vocals·instrumental 각각의 파일 크기·SHA-256·sample rate·channel·duration·peak·RMS·near-silence·clipped sample ratio를 기록한다. 필수 계약은 파일 존재, 48kHz, Stereo, 두 Stem 동일 길이, RMS 기준 비무음, clipping 없음이다. 분리 누출을 신뢰성 있게 자동 판정할 기준 음원이 없으므로 수동 평가로 남긴다.

청취 평가는 왜곡, 잡음, 보컬 명료도, 반주 손상, 균형, 전체 자연스러움을 익명화된 고정 척도로 기록한다. Stem 전용 양식은 [EVAL-002](../../reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md)를 사용한다.
