import { Badge } from "@/components/ui";
import {
  formatAudioDuration,
  formatSampleRate,
  type AudioAnalysisSummary,
} from "@/lib/audio-analysis";

export function AudioQualitySummary({
  analysis,
  compact = false,
}: {
  analysis: AudioAnalysisSummary | null;
  compact?: boolean;
}) {
  if (compact) return <CompactAudioQuality analysis={analysis} />;
  if (!analysis) {
    return (
      <section className="audio-quality" aria-labelledby="audio-quality-title">
        <h3 id="audio-quality-title">오디오 분석</h3>
        <p className="muted">이 음원에는 품질 분석 정보가 없습니다.</p>
      </section>
    );
  }
  const quality = analysis.quality;
  return (
    <section className="audio-quality" aria-labelledby="audio-quality-title">
      <div className="result-head">
        <h3 id="audio-quality-title">오디오 분석</h3>
        <Badge tone={statusTone(analysis.status)}>{statusLabel(analysis.status)}</Badge>
      </div>
      {analysis.status === "PENDING" && (
        <p className="muted" aria-live="polite">품질을 분석하고 있습니다.</p>
      )}
      {analysis.status === "PARTIAL" && (
        <p className="audio-quality-notice">일부 항목을 분석하지 못했습니다.</p>
      )}
      {analysis.status === "FAILED" && (
        <p className="audio-quality-notice">음원은 정상적으로 생성됐지만 품질 분석을 완료하지 못했습니다.</p>
      )}
      {analysis.status === "UNSUPPORTED" && (
        <p className="audio-quality-notice">현재 형식은 품질 분석을 지원하지 않습니다.</p>
      )}
      {quality && (
        <dl className="metadata-list">
          <Metric label="길이" value={formatAudioDuration(quality.durationSeconds)} />
          <Metric label="샘플레이트" value={formatSampleRate(quality.sampleRate)} />
          <Metric label="채널" value={quality.channels === 1 ? "모노" : quality.channels === 2 ? "스테레오" : `${quality.channels}채널`} />
          <Metric label="최대 음량" value={formatLevel(quality.samplePeakDbfs, "dBFS")} />
          <Metric label="클리핑" value={quality.clippingDetected ? `감지됨 (${quality.clippingSampleCount.toLocaleString("ko-KR")} samples)` : "감지되지 않음"} />
          <Metric label="통합 음량" value={formatLevel(quality.integratedLufs, "LUFS")} />
        </dl>
      )}
      {analysis.warnings.length > 0 && (
        <ul className="audio-quality-warnings" aria-label="오디오 분석 안내">
          {analysis.warnings.map((warning) => <li key={warning}>{warning}</li>)}
        </ul>
      )}
    </section>
  );
}

function CompactAudioQuality({ analysis }: { analysis: AudioAnalysisSummary | null }) {
  if (!analysis) return <span className="audio-quality-compact">분석 정보 없음</span>;
  const clipping = analysis.quality?.clippingDetected;
  const lufs = analysis.quality?.integratedLufs;
  return (
    <span className="audio-quality-compact">
      분석 {statusLabel(analysis.status)}
      {clipping === true ? " · 클리핑 감지" : clipping === false ? " · 클리핑 없음" : ""}
      {lufs !== null && lufs !== undefined ? ` · ${lufs.toFixed(1)} LUFS` : ""}
    </span>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function formatLevel(value: number | null, unit: string): string {
  return value === null ? "측정 불가" : `${value.toFixed(1)} ${unit}`;
}

function statusLabel(status: AudioAnalysisSummary["status"]): string {
  if (status === "COMPLETED") return "완료";
  if (status === "PARTIAL") return "일부 완료";
  if (status === "FAILED") return "분석 실패";
  if (status === "UNSUPPORTED") return "미지원";
  if (status === "PENDING") return "분석 중";
  return "요청되지 않음";
}

function statusTone(status: AudioAnalysisSummary["status"]): string {
  if (status === "COMPLETED") return "success";
  if (status === "FAILED") return "error";
  if (status === "PENDING") return "active";
  return "neutral";
}
