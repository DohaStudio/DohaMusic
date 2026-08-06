# 오디오 품질 지표

> 문서 목적: 자동 검사와 청취 평가 항목을 정의한다.
> 현재 상태: **Stem·Voice 자동 검사 분석 / 사용자 청취 평가 대기**

자동 검사 후보는 파일 디코딩, 길이, 샘플레이트, 피크·클리핑, 무음 비율, loudness, 분리 누출 지표다. 단일 자동 지표로 음악 품질을 확정하지 않는다.

EXP-003 실행기는 vocals·instrumental 각각의 파일 크기·SHA-256·sample rate·channel·duration·peak·RMS·near-silence·clipped sample ratio를 기록한다. 필수 계약은 파일 존재, 48kHz, Stereo, 두 Stem 동일 길이, RMS 기준 비무음, clipping 없음이다. 분리 누출을 신뢰성 있게 자동 판정할 기준 음원이 없으므로 수동 평가로 남긴다.

청취 평가는 왜곡, 잡음, 보컬 명료도, 반주 손상, 균형, 전체 자연스러움을 익명화된 고정 척도로 기록한다. Stem 전용 양식은 [EVAL-002](../../reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md)를 사용한다.

Voice Conversion은 길이, 파일 크기, SHA-256, sample rate, channel, peak, RMS, near-silence와 clipped sample ratio를 기록한다. LUFS 도구가 없는 실행에서는 LUFS를 비워 두며 RMS로 대체하지 않는다. float WAV의 1.0 초과는 over-range 위험이고 정수 PCM의 비가역 clipping과 구분한다. 운영 판정 전에는 모델 출력, resample 후, PCM export 후 지표를 각각 측정하고 true-peak 기준을 정의해야 한다.

음색 유사도·발음·노래 자연스러움·호흡·고음·노이즈·활용 가능성은 [EVAL-003](../../reports/evaluations/EVAL-003-seed-vc-listening-evaluation.md)에 사용자가 기록한다. 자동 지표만으로 Voice Provider를 승인하지 않는다.

Mixer 출력은 sample peak·RMS·headroom·clipping ratio·over-range·silence·길이·sample rate·channels를 기록한다. 보호 전 합산 신호와 PCM 직전 신호를 구분하고, 현재 계산하지 않는 True Peak와 LUFS는 `미지원`으로 표시한다. volume·balance·naturalness·noise·clipping 청감은 [EVAL-004](../../reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md)에 사용자가 기록한다.
