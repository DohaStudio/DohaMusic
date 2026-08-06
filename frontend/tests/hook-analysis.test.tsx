import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HookSummary } from "@/features/audio/hook-summary";
import { parseAudioAnalysis } from "@/lib/audio-analysis";

const completed = {
  audio_analysis_version: "1.0",
  analysis_status: "COMPLETED",
  quality: null,
  tempo: null,
  hook: {
    hook_analysis_version: "1.0",
    status: "COMPLETED",
    candidate: {
      start_seconds: 42.1,
      end_seconds: 57,
      duration_seconds: 14.9,
      confidence: 0.74,
      selection_strategy: "energy_repetition",
      raw_frame_scores: [0.2, 0.8],
    },
    source_path: "D:/private/final.wav",
  },
  warnings: [],
};

describe("hook analysis allowlist parser", () => {
  it("후렴 후보만 camelCase 공개 요약으로 변환한다", () => {
    expect(parseAudioAnalysis(completed)?.hook).toEqual({
      version: "1.0",
      status: "COMPLETED",
      candidate: {
        startSeconds: 42.1,
        endSeconds: 57,
        durationSeconds: 14.9,
        confidence: 0.74,
        selectionStrategy: "energy_repetition",
      },
    });
  });

  it.each(["PARTIAL", "FAILED", "UNSUPPORTED"] as const)(
    "%s 상태를 보존한다",
    (status) => {
      const analysis = parseAudioAnalysis({
        ...completed,
        analysis_status: status,
        hook: { hook_analysis_version: "1.0", status, candidate: null },
      });
      expect(analysis?.hook?.status).toBe(status);
      expect(analysis?.hook?.candidate).toBeNull();
    },
  );

  it("잘못된 confidence와 strategy를 거부한다", () => {
    expect(
      parseAudioAnalysis({
        ...completed,
        hook: {
          ...completed.hook,
          candidate: { ...completed.hook.candidate, confidence: 2 },
        },
      }),
    ).toBeNull();
    expect(
      parseAudioAnalysis({
        ...completed,
        hook: {
          ...completed.hook,
          candidate: {
            ...completed.hook.candidate,
            selection_strategy: "chorus_exact",
          },
        },
      }),
    ).toBeNull();
  });
});

describe("HookSummary", () => {
  it("Result에서 추정 구간과 신뢰도를 표시한다", () => {
    render(<HookSummary analysis={parseAudioAnalysis(completed)} />);
    expect(screen.getByRole("heading", { name: "후렴 후보" })).toBeInTheDocument();
    expect(screen.getByText("추정 구간")).toBeInTheDocument();
    expect(screen.getByText("00:42~00:57")).toBeInTheDocument();
    expect(screen.getByText("Medium (0.74)")).toBeInTheDocument();
    expect(screen.queryByText(/정확한 후렴|후렴입니다/)).not.toBeInTheDocument();
  });

  it("History 목록은 후보 유무만 표시한다", () => {
    const { rerender } = render(
      <HookSummary analysis={parseAudioAnalysis(completed)} mode="status" />,
    );
    expect(screen.getByText("후렴 후보 있음")).toBeInTheDocument();
    expect(screen.queryByText("00:42~00:57")).not.toBeInTheDocument();

    rerender(
      <HookSummary
        analysis={parseAudioAnalysis({
          ...completed,
          analysis_status: "PARTIAL",
          hook: {
            ...completed.hook,
            status: "PARTIAL",
            candidate: {
              ...completed.hook.candidate,
              confidence: 0.2,
              selection_strategy: "fallback_middle",
            },
          },
        })}
        mode="status"
      />,
    );
    expect(screen.getByText("후렴 후보 없음")).toBeInTheDocument();
  });

  it("Project 상세 요약에 추정 구간을 표시한다", () => {
    render(<HookSummary analysis={parseAudioAnalysis(completed)} mode="summary" />);
    expect(screen.getByText(/후렴 후보 · 추정 구간 00:42~00:57/)).toBeInTheDocument();
  });

  it("실패와 구형 결과를 안전하게 안내한다", () => {
    const { rerender } = render(
      <HookSummary
        analysis={parseAudioAnalysis({
          ...completed,
          analysis_status: "FAILED",
          hook: { hook_analysis_version: "1.0", status: "FAILED", candidate: null },
        })}
      />,
    );
    expect(screen.getByText("후렴 후보를 추정하지 못했습니다.")).toBeInTheDocument();
    rerender(<HookSummary analysis={null} />);
    expect(screen.getByText("이 결과에는 후렴 후보 분석 정보가 없습니다.")).toBeInTheDocument();
  });
});
