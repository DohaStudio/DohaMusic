import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AudioQualitySummary } from "@/features/audio/audio-quality-summary";
import {
  formatAudioDuration,
  formatSampleRate,
  parseAudioAnalysis,
} from "@/lib/audio-analysis";

const completed = {
  audio_analysis_version: "1.0",
  analysis_status: "COMPLETED",
  quality: {
    duration_seconds: 60.01,
    sample_rate: 44_100,
    channels: 2,
    sample_peak_dbfs: -1.2,
    clipping_detected: false,
    clipping_sample_count: 0,
    clipping_ratio: 0,
    integrated_lufs: -13.8,
  },
  warnings: [],
  source_file_role: "final_mix",
  source_path: "D:/private/final.wav",
};

describe("audio analysis allowlist parser", () => {
  it("COMPLETED 지표를 camelCase 요약으로 변환한다", () => {
    expect(parseAudioAnalysis(completed)).toEqual({
      version: "1.0",
      status: "COMPLETED",
      quality: {
        durationSeconds: 60.01,
        sampleRate: 44_100,
        channels: 2,
        samplePeakDbfs: -1.2,
        clippingDetected: false,
        clippingSampleCount: 0,
        clippingRatio: 0,
        integratedLufs: -13.8,
      },
      tempo: null,
      warnings: [],
    });
  });

  it.each(["PARTIAL", "FAILED"] as const)("%s 상태를 파싱한다", (status) => {
    const parsed = parseAudioAnalysis({
      ...completed,
      analysis_status: status,
      quality: status === "FAILED" ? null : completed.quality,
      warnings: ["안전한 안내"],
    });
    expect(parsed?.status).toBe(status);
    expect(parsed?.warnings).toEqual(["안전한 안내"]);
  });

  it("구형·잘못된 metadata와 비유한 수치를 거부한다", () => {
    expect(parseAudioAnalysis({})).toBeNull();
    expect(parseAudioAnalysis({ ...completed, audio_analysis_version: "99.0" })).toBeNull();
    expect(parseAudioAnalysis({ ...completed, quality: { ...completed.quality, integrated_lufs: Infinity } })).toBeNull();
    expect(parseAudioAnalysis({ ...completed, quality: { ...completed.quality, clipping_ratio: 2 } })).toBeNull();
    expect(parseAudioAnalysis({ ...completed, warnings: [{ stack: "private" }] })).toBeNull();
  });

  it("표시 형식에 단위와 채널 친화 표현을 제공한다", () => {
    expect(formatAudioDuration(60.01)).toBe("1분 00초");
    expect(formatSampleRate(44_100)).toBe("44.1 kHz");
  });
});

describe("AudioQualitySummary", () => {
  it("전체 품질 지표와 단위를 표시한다", () => {
    render(<AudioQualitySummary analysis={parseAudioAnalysis(completed)} />);
    expect(screen.getByRole("heading", { name: "오디오 분석" })).toBeInTheDocument();
    expect(screen.getByText("스테레오")).toBeInTheDocument();
    expect(screen.getByText("-1.2 dBFS")).toBeInTheDocument();
    expect(screen.getByText("-13.8 LUFS")).toBeInTheDocument();
    expect(screen.getByText("감지되지 않음")).toBeInTheDocument();
  });

  it("PARTIAL 경고와 클리핑을 텍스트로 전달한다", () => {
    const analysis = parseAudioAnalysis({
      ...completed,
      analysis_status: "PARTIAL",
      quality: { ...completed.quality, clipping_detected: true, clipping_sample_count: 4 },
      warnings: ["일부 구간에서 소리가 과도하게 커 왜곡될 수 있습니다."],
    });
    render(<AudioQualitySummary analysis={analysis} />);
    expect(screen.getByText("일부 항목을 분석하지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByText(/감지됨 \(4 samples\)/)).toBeInTheDocument();
  });

  it("실패와 구형 Result fallback을 표시한다", () => {
    const { rerender } = render(
      <AudioQualitySummary analysis={parseAudioAnalysis({ ...completed, analysis_status: "FAILED", quality: null })} />,
    );
    expect(screen.getByText(/음원은 정상적으로 생성됐지만/)).toBeInTheDocument();
    rerender(<AudioQualitySummary analysis={null} />);
    expect(screen.getByText("이 음원에는 품질 분석 정보가 없습니다.")).toBeInTheDocument();
  });
});
