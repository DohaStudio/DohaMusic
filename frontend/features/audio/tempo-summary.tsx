import { Badge } from "@/components/ui";
import {
  tempoConfidenceLabel,
  type AudioAnalysisSummary,
} from "@/lib/audio-analysis";

type TempoMode = "status" | "summary" | "detail";

export function TempoSummary({
  analysis,
  mode = "detail",
}: {
  analysis: AudioAnalysisSummary | null;
  mode?: TempoMode;
}) {
  const tempo = analysis?.tempo ?? null;
  if (mode === "status") {
    return (
      <span className="audio-quality-compact">
        Tempo {tempo ? statusLabel(tempo.status) : "Unavailable"}
      </span>
    );
  }
  if (mode === "summary") {
    return (
      <span className="audio-quality-compact">
        Tempo {tempo ? statusLabel(tempo.status) : "Unavailable"}
        {tempo?.detectedBpm != null
          ? ` · 예상 템포는 약 ${tempo.detectedBpm.toFixed(1)} BPM`
          : ""}
        {tempo?.confidence != null
          ? ` · 신뢰도 ${tempoConfidenceLabel(tempo.confidence)}`
          : ""}
      </span>
    );
  }
  return (
    <section className="audio-quality" aria-labelledby="tempo-title">
      <div className="result-head">
        <h3 id="tempo-title">Tempo 분석</h3>
        <Badge tone={statusTone(tempo?.status)}>
          {tempo ? statusLabel(tempo.status) : "Unavailable"}
        </Badge>
      </div>
      {!tempo ? (
        <p className="muted">이 결과에는 Tempo 분석 정보가 없습니다.</p>
      ) : tempo.detectedBpm == null ? (
        <p className="audio-quality-notice">Tempo를 추정하지 못했습니다.</p>
      ) : (
        <>
          <p>예상 템포는 약 {tempo.detectedBpm.toFixed(1)} BPM입니다.</p>
          <dl className="metadata-list">
            <Metric label="요청 BPM" value={formatBpm(tempo.requestedBpm)} />
            <Metric label="추정 BPM" value={formatBpm(tempo.detectedBpm)} />
            <Metric
              label="신뢰도"
              value={`${tempoConfidenceLabel(tempo.confidence)}${tempo.confidence == null ? "" : ` (${tempo.confidence.toFixed(2)})`}`}
            />
            <Metric label="차이" value={formatSignedError(tempo.bpmError)} />
            <Metric label="절대 오차" value={formatError(tempo.absoluteBpmError)} />
          </dl>
          {(tempo.halfTimeCandidate || tempo.doubleTimeCandidate) && (
            <p className="audio-quality-notice">
              {tempo.halfTimeCandidate
                ? "Half-time 후보로 해석될 수 있습니다."
                : "Double-time 후보로 해석될 수 있습니다."}
            </p>
          )}
        </>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function formatBpm(value: number | null): string {
  return value === null ? "Unavailable" : `${value.toFixed(1)} BPM`;
}

function formatError(value: number | null): string {
  return value === null ? "Unavailable" : `${value.toFixed(1)} BPM`;
}

function formatSignedError(value: number | null): string {
  if (value === null) return "Unavailable";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)} BPM`;
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
