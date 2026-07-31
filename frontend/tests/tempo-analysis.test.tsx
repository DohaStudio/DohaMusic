import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TempoSummary } from "@/features/audio/tempo-summary";
import {
  parseAudioAnalysis,
  tempoConfidenceLabel,
} from "@/lib/audio-analysis";

const analysis = {
  audio_analysis_version: "1.0",
  analysis_status: "COMPLETED",
  quality: null,
  tempo: {
    version: "1.0",
    status: "COMPLETED",
    requested_bpm: 120,
    detected_bpm: 119.8,
    confidence: 0.91,
    bpm_error: -0.2,
    absolute_bpm_error: 0.2,
    half_time_candidate: false,
    double_time_candidate: false,
    raw_onset_envelope: [0.1, 0.8],
    source_path: "D:/private/final.wav",
  },
  warnings: [],
};

describe("Tempo Analysis parser", () => {
  it("공개 필드만 camelCase 요약으로 변환한다", () => {
    expect(parseAudioAnalysis(analysis)?.tempo).toEqual({
      version: "1.0",
      status: "COMPLETED",
      requestedBpm: 120,
      detectedBpm: 119.8,
      confidence: 0.91,
      bpmError: -0.2,
      absoluteBpmError: 0.2,
      halfTimeCandidate: false,
      doubleTimeCandidate: false,
    });
    expect(JSON.stringify(parseAudioAnalysis(analysis))).not.toContain("private");
    expect(JSON.stringify(parseAudioAnalysis(analysis))).not.toContain("onset");
  });

  it.each(["PARTIAL", "FAILED"] as const)("%s 상태를 보존한다", (status) => {
    const parsed = parseAudioAnalysis({
      ...analysis,
      tempo: {
        ...analysis.tempo,
        status,
        detected_bpm: status === "FAILED" ? null : 119.8,
        confidence: status === "FAILED" ? null : 0.3,
        bpm_error: status === "FAILED" ? null : -0.2,
        absolute_bpm_error: status === "FAILED" ? null : 0.2,
      },
    });
    expect(parsed?.tempo?.status).toBe(status);
  });

  it("잘못된 신뢰도와 무한대 값을 거부한다", () => {
    expect(parseAudioAnalysis({ ...analysis, tempo: { ...analysis.tempo, confidence: 2 } })).toBeNull();
    expect(parseAudioAnalysis({ ...analysis, tempo: { ...analysis.tempo, detected_bpm: Infinity } })).toBeNull();
  });

  it("신뢰도 경계를 High, Medium, Low, Unavailable로 표시한다", () => {
    expect(tempoConfidenceLabel(0.8)).toBe("High");
    expect(tempoConfidenceLabel(0.5)).toBe("Medium");
    expect(tempoConfidenceLabel(0.49)).toBe("Low");
    expect(tempoConfidenceLabel(null)).toBe("Unavailable");
  });
});

describe("TempoSummary", () => {
  it("Result 상세에서 추정 표현과 오차를 표시한다", () => {
    render(<TempoSummary analysis={parseAudioAnalysis(analysis)} />);
    expect(screen.getByRole("heading", { name: "Tempo 분석" })).toBeInTheDocument();
    expect(screen.getByText("예상 템포는 약 119.8 BPM입니다.")).toBeInTheDocument();
    expect(screen.getByText("High (0.91)")).toBeInTheDocument();
    expect(screen.getByText("-0.2 BPM")).toBeInTheDocument();
    expect(screen.queryByText(/정확한 BPM/)).not.toBeInTheDocument();
  });

  it("History에는 상태만 표시한다", () => {
    render(<TempoSummary mode="status" analysis={parseAudioAnalysis(analysis)} />);
    expect(screen.getByText("Tempo 완료")).toBeInTheDocument();
    expect(screen.queryByText(/119\.8/)).not.toBeInTheDocument();
  });

  it("Project 요약에는 추정값을 표시한다", () => {
    render(<TempoSummary mode="summary" analysis={parseAudioAnalysis(analysis)} />);
    expect(screen.getByText(/예상 템포는 약 119\.8 BPM/)).toBeInTheDocument();
  });

  it("실패 및 구형 결과는 Unavailable fallback을 표시한다", () => {
    const failed = parseAudioAnalysis({
      ...analysis,
      tempo: {
        ...analysis.tempo,
        status: "FAILED",
        detected_bpm: null,
        confidence: null,
        bpm_error: null,
        absolute_bpm_error: null,
      },
    });
    const { rerender } = render(<TempoSummary analysis={failed} />);
    expect(screen.getByText("Tempo를 추정하지 못했습니다.")).toBeInTheDocument();
    rerender(<TempoSummary analysis={parseAudioAnalysis({ ...analysis, tempo: null })} />);
    expect(screen.getByText("이 결과에는 Tempo 분석 정보가 없습니다.")).toBeInTheDocument();
  });
});
