"use client";

import { AudioLines, Check, Pause, Play, Star, Trash2, Volume2 } from "lucide-react";
import { type ReactNode, useRef, useState } from "react";
import { Badge, Button, Progress } from "@/components/ui";
import type { VoiceEnrollmentSampleDto } from "./voice-enrollment-types";

function qualityTone(status: VoiceEnrollmentSampleDto["quality"]["status"]) {
  if (status === "PASS") return "success";
  if (status === "WARNING") return "warning";
  return "danger";
}

function formatPlaybackTime(seconds: number) {
  if (!Number.isFinite(seconds)) return "00:00";
  const safeSeconds = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(safeSeconds / 60)).padStart(2, "0")}:${String(safeSeconds % 60).padStart(2, "0")}`;
}

export function VoiceAudioPlayer({ src, label }: { src: string; label: string }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const toggle = async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) await audio.play();
    else audio.pause();
  };

  return (
    <div className="voice-audio-player" aria-label={`${label} 미리 듣기`}>
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
      />
      <button type="button" className="audio-play-button" onClick={() => void toggle()} aria-label={playing ? `${label} 일시정지` : `${label} 재생`}>
        {playing ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
      </button>
      <label className="audio-position">
        <span className="sr-only">{label} 재생 위치</span>
        <input
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={Math.min(currentTime, duration || 0)}
          aria-label={`${label} 재생 위치`}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (audioRef.current) audioRef.current.currentTime = next;
            setCurrentTime(next);
          }}
        />
      </label>
      <time>{formatPlaybackTime(currentTime)} / {formatPlaybackTime(duration)}</time>
      <label className="audio-volume">
        <Volume2 aria-hidden="true" />
        <span className="sr-only">{label} 볼륨</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          defaultValue={1}
          aria-label={`${label} 볼륨`}
          onChange={(event) => { if (audioRef.current) audioRef.current.volume = Number(event.target.value); }}
        />
      </label>
    </div>
  );
}

export function VoiceSampleCard({
  sample,
  label,
  previewUrl,
  selected,
  selectionMode = "button",
  deleting,
  onSelect,
  onDelete,
}: {
  sample: VoiceEnrollmentSampleDto;
  label: string;
  previewUrl?: string;
  selected?: boolean;
  selectionMode?: "button" | "radio" | "none";
  deleting?: boolean;
  onSelect?: () => void;
  onDelete?: () => void;
}) {
  const eligible = sample.submit_eligible;
  return (
    <article className={`voice-sample-card quality-${sample.quality.status.toLowerCase()}${selected ? " selected" : ""}`} aria-label={`${label}, 품질 ${sample.quality.status}`}>
      <div className="voice-sample-card-heading">
        <div>
          <span className="sample-source">{sample.source_type === "BROWSER_RECORDING" ? "브라우저 녹음" : "파일 업로드"}</span>
          <strong>{label}</strong>
        </div>
        <Badge tone={qualityTone(sample.quality.status)}>{sample.quality.status}</Badge>
      </div>
      <div className="voice-sample-meta">
        <span>{sample.duration_seconds?.toFixed(1) ?? "—"}초</span>
        <span>{sample.normalized_content_type ?? sample.original_content_type ?? "형식 확인 중"}</span>
      </div>
      {previewUrl ? <VoiceAudioPlayer src={previewUrl} label={label} /> : <p className="sample-preview-unavailable"><AudioLines aria-hidden="true" /> 이 기기에서 추가한 Sample은 여기서 미리 들을 수 있습니다.</p>}
      <div className="voice-sample-actions">
        {selectionMode === "radio" && <label className="sample-reference-radio"><input type="radio" name="reference-sample" aria-label={`${label} 대표 Sample 선택`} checked={Boolean(selected)} disabled={!eligible || deleting} onChange={onSelect} /><span>{selected ? "대표 Sample" : "대표로 선택"}</span></label>}
        {selectionMode === "button" && <Button type="button" className={selected ? "secondary selected-reference" : "secondary"} disabled={!eligible || deleting} aria-pressed={Boolean(selected)} onClick={onSelect}>{selected ? <><Check aria-hidden="true" /> 대표 Sample</> : <><Star aria-hidden="true" /> 대표로 선택</>}</Button>}
        {onDelete && <Button type="button" className="danger" disabled={deleting || sample.status === "PROMOTED"} aria-label={`${label} 삭제`} onClick={onDelete}><Trash2 aria-hidden="true" /> {deleting ? "삭제 중…" : "삭제"}</Button>}
      </div>
    </article>
  );
}

export function EnrollmentSummary({
  samples,
  selectedLabel,
  nextStep,
  children,
}: {
  samples: VoiceEnrollmentSampleDto[];
  selectedLabel?: string;
  nextStep: string;
  children?: ReactNode;
}) {
  const pass = samples.filter((sample) => sample.quality.status === "PASS").length;
  const warning = samples.filter((sample) => sample.quality.status === "WARNING").length;
  const fail = samples.filter((sample) => sample.quality.status === "FAIL").length;
  return (
    <aside className="enrollment-summary" aria-label="현재 음성 등록 요약">
      <div className="summary-heading"><span>현재 등록</span><strong>{samples.length} / 10 <small>Sample</small></strong></div>
      <Progress value={samples.length * 10} label={`Sample ${samples.length}개 등록됨`} />
      <dl className="summary-quality">
        <div><dt><span className="quality-dot pass" />PASS</dt><dd>{pass}</dd></div>
        <div><dt><span className="quality-dot warning" />WARNING</dt><dd>{warning}</dd></div>
        <div><dt><span className="quality-dot fail" />FAIL</dt><dd>{fail}</dd></div>
      </dl>
      <div className="summary-reference"><span>대표 Sample</span><strong>{selectedLabel ?? "아직 선택하지 않음"}</strong></div>
      <div className="summary-next"><span>다음 단계</span><strong>{nextStep}</strong></div>
      {children}
    </aside>
  );
}

export function EnrollmentOperationProgress({ label, value }: { label: string; value: number }) {
  return <div className="enrollment-operation" role="status" aria-live="polite"><span className="skeleton-line" aria-hidden="true" /><div><strong>{label}</strong><Progress value={value} label={label} /></div></div>;
}
