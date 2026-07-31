import { Badge } from "@/components/ui";
import {
  analysisConfidenceLabel,
  type AudioAnalysisSummary,
  type HookAnalysisSummary,
  type HookSelectionStrategy,
} from "@/lib/audio-analysis";

type HookMode = "status" | "summary" | "detail";

export function HookSummary({
  analysis,
  mode = "detail",
}: {
  analysis: AudioAnalysisSummary | null;
  mode?: HookMode;
}) {
  const hook = analysis?.hook ?? null;
  const detected = hasDetectedCandidate(hook);

  if (mode === "status") {
    return (
      <span className="audio-quality-compact">
        {detected ? "후렴 후보 있음" : "후렴 후보 없음"}
      </span>
    );
  }

  if (mode === "summary") {
    return (
      <span className="audio-quality-compact">
        {detected && hook?.candidate
          ? `후렴 후보 · 추정 구간 ${formatRange(hook.candidate.startSeconds, hook.candidate.endSeconds)} · 신뢰도 ${analysisConfidenceLabel(hook.candidate.confidence)}`
          : "후렴 후보 없음"}
      </span>
    );
  }

  return (
    <section className="audio-quality" aria-labelledby="hook-title">
      <div className="result-head">
        <h3 id="hook-title">후렴 후보</h3>
        <Badge tone={statusTone(hook?.status)}>
          {hook ? statusLabel(hook.status) : "Unavailable"}
        </Badge>
      </div>
      {!hook ? (
        <p className="muted">이 결과에는 후렴 후보 분석 정보가 없습니다.</p>
      ) : !hook.candidate ? (
        <p className="audio-quality-notice">후렴 후보를 추정하지 못했습니다.</p>
      ) : (
        <>
          <p>
            {detected
              ? "에너지와 반복 패턴으로 찾은 추정 구간입니다."
              : "신뢰도가 낮아 곡 중앙의 대체 구간으로 표시합니다."}
          </p>
          <dl className="metadata-list">
            <Metric
              label={detected ? "추정 구간" : "중앙 대체 구간"}
              value={formatRange(
                hook.candidate.startSeconds,
                hook.candidate.endSeconds,
              )}
            />
            <Metric
              label="길이"
              value={`${hook.candidate.durationSeconds.toFixed(1)}초`}
            />
            <Metric
              label="신뢰도"
              value={`${analysisConfidenceLabel(hook.candidate.confidence)} (${hook.candidate.confidence.toFixed(2)})`}
            />
            <Metric
              label="선정 방식"
              value={strategyLabel(hook.candidate.selectionStrategy)}
            />
          </dl>
        </>
      )}
    </section>
  );
}

function hasDetectedCandidate(hook: HookAnalysisSummary | null): boolean {
  const strategy = hook?.candidate?.selectionStrategy;
  return strategy === "energy_repetition" || strategy === "energy_peak";
}

function formatRange(start: number, end: number): string {
  return `${formatTimestamp(start)}~${formatTimestamp(end)}`;
}

function formatTimestamp(seconds: number): string {
  const rounded = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(rounded / 60);
  return `${minutes.toString().padStart(2, "0")}:${(rounded % 60).toString().padStart(2, "0")}`;
}

function strategyLabel(strategy: HookSelectionStrategy): string {
  if (strategy === "energy_repetition") return "에너지·반복";
  if (strategy === "energy_peak") return "에너지 피크";
  if (strategy === "fallback_middle") return "곡 중앙 fallback";
  return "Unavailable";
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function statusLabel(status: AudioAnalysisSummary["status"]): string {
  if (status === "COMPLETED") return "완료";
  if (status === "PARTIAL") return "부분 완료";
  if (status === "FAILED") return "실패";
  if (status === "UNSUPPORTED") return "미지원";
  if (status === "PENDING") return "분석 중";
  return "요청되지 않음";
}

function statusTone(status: AudioAnalysisSummary["status"] | undefined): string {
  if (status === "COMPLETED") return "success";
  if (status === "FAILED") return "error";
  if (status === "PENDING") return "active";
  return "neutral";
}
