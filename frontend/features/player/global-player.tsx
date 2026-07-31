"use client";

import { useEffect, useRef, useState } from "react";
import { usePlayerStore } from "@/stores/player-store";

export function GlobalPlayer() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const currentFile = usePlayerStore((state) => state.currentFile);
  const shouldPlay = usePlayerStore((state) => state.shouldPlay);
  const play = usePlayerStore((state) => state.play);
  const pause = usePlayerStore((state) => state.pause);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !currentFile) return;
    if (shouldPlay) {
      audio.play().catch(() => {
        pause();
        setError("오디오를 재생할 수 없습니다.");
      });
    } else {
      audio.pause();
    }
  }, [currentFile, pause, shouldPlay]);

  return (
    <footer className="player-shell" aria-label="Doha Studio Player">
      <div className="mini-art">D</div>
      <div className="player-copy">
        <strong>{currentFile?.fileType ?? "재생할 결과를 선택하세요"}</strong>
        <small>
          {error ||
            (loading
              ? "오디오 로딩 중"
              : (currentFile?.mimeType ??
                "Result에서 Audio를 선택할 수 있습니다"))}
        </small>
      </div>
      <audio
        ref={audioRef}
        src={currentFile?.contentUrl}
        preload="metadata"
        onLoadStart={() => {
          setLoading(true);
          setError("");
        }}
        onLoadedMetadata={(event) => {
          setDuration(event.currentTarget.duration || 0);
          setLoading(false);
        }}
        onTimeUpdate={(event) =>
          setCurrentTime(event.currentTarget.currentTime)
        }
        onEnded={pause}
        onError={() => {
          setLoading(false);
          setError("오디오를 불러오지 못했습니다.");
          pause();
        }}
      />
      <button
        type="button"
        disabled={!currentFile}
        aria-label={shouldPlay ? "일시정지" : "재생"}
        onClick={() => {
          if (!currentFile) return;
          if (shouldPlay) pause();
          else play(currentFile);
        }}
      >
        {shouldPlay ? "Ⅱ" : "▶"}
      </button>
      <label className="player-seek">
        <span className="sr-only">재생 위치</span>
        <input
          aria-label="재생 위치"
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={Math.min(currentTime, duration || 0)}
          disabled={!currentFile || !duration}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (audioRef.current) audioRef.current.currentTime = next;
            setCurrentTime(next);
          }}
        />
        <small>
          {formatTime(currentTime)} / {formatTime(duration)}
        </small>
      </label>
      <button
        type="button"
        disabled={!currentFile}
        aria-label={muted ? "음소거 해제" : "음소거"}
        onClick={() => {
          const next = !muted;
          setMuted(next);
          if (audioRef.current) audioRef.current.muted = next;
        }}
      >
        {muted ? "🔇" : "🔊"}
      </button>
      <label className="player-volume">
        <span className="sr-only">볼륨</span>
        <input
          aria-label="볼륨"
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={volume}
          disabled={!currentFile}
          onChange={(event) => {
            const next = Number(event.target.value);
            setVolume(next);
            if (audioRef.current) audioRef.current.volume = next;
          }}
        />
      </label>
    </footer>
  );
}

function formatTime(value: number) {
  if (!Number.isFinite(value)) return "0:00";
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${seconds}`;
}
