"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  MAX_VOICE_DURATION_SECONDS,
} from "./voice-enrollment-types";
import { selectMediaRecorderMime } from "./voice-enrollment-utils";

export type RecorderStatus =
  | "IDLE"
  | "REQUESTING_PERMISSION"
  | "READY"
  | "RECORDING"
  | "PAUSED"
  | "STOPPING"
  | "PREVIEW"
  | "FAILED";

export interface VoiceRecording {
  blob: Blob;
  previewUrl: string;
  durationSeconds: number;
  mimeType: string;
}

function microphoneErrorMessage(error: unknown): string {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "마이크 권한이 차단되었습니다. 브라우저 주소창의 권한 설정에서 마이크를 허용해 주세요.";
  }
  if (name === "NotFoundError") return "사용할 수 있는 마이크를 찾지 못했습니다. 장치를 연결하거나 WAV 파일을 업로드해 주세요.";
  if (name === "NotReadableError") return "마이크가 다른 프로그램에서 사용 중일 수 있습니다. 장치를 확인해 주세요.";
  return "마이크를 준비하지 못했습니다. WAV 파일 업로드를 이용해 주세요.";
}

export function useVoiceRecorder() {
  const [status, setStatus] = useState<RecorderStatus>("IDLE");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<string>();
  const [recording, setRecording] = useState<VoiceRecording>();
  const streamRef = useRef<MediaStream | undefined>(undefined);
  const recorderRef = useRef<MediaRecorder | undefined>(undefined);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const frameRef = useRef<number | undefined>(undefined);
  const audioContextRef = useRef<AudioContext | undefined>(undefined);
  const previewUrlRef = useRef<string | undefined>(undefined);
  const elapsedRef = useRef(0);

  const stopTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = undefined;
  }, []);

  const stopLevel = useCallback(() => {
    if (frameRef.current) cancelAnimationFrame(frameRef.current);
    frameRef.current = undefined;
    setLevel(0);
    const context = audioContextRef.current;
    audioContextRef.current = undefined;
    if (context && context.state !== "closed") void context.close();
  }, []);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = undefined;
    stopLevel();
  }, [stopLevel]);

  const clearPreview = useCallback(() => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = undefined;
    setRecording(undefined);
  }, []);

  const monitorLevel = useCallback((stream: MediaStream) => {
    const AudioContextConstructor = window.AudioContext;
    if (!AudioContextConstructor) return;
    const context = new AudioContextConstructor();
    audioContextRef.current = context;
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    context.createMediaStreamSource(stream).connect(analyser);
    const values = new Uint8Array(analyser.frequencyBinCount);
    const update = () => {
      analyser.getByteTimeDomainData(values);
      let sum = 0;
      for (const value of values) {
        const normalized = (value - 128) / 128;
        sum += normalized * normalized;
      }
      setLevel(Math.min(1, Math.sqrt(sum / values.length) * 4));
      frameRef.current = requestAnimationFrame(update);
    };
    update();
  }, []);

  const requestPermission = useCallback(async () => {
    setError(undefined);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setStatus("FAILED");
      setError("이 브라우저에서는 음성 녹음을 지원하지 않습니다. WAV 파일을 업로드해 주세요.");
      return;
    }
    if (!window.isSecureContext) {
      setStatus("FAILED");
      setError("마이크 녹음은 HTTPS 또는 localhost에서만 사용할 수 있습니다. WAV 파일을 업로드해 주세요.");
      return;
    }
    setStatus("REQUESTING_PERMISSION");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;
      stream.getAudioTracks().forEach((track) => {
        track.addEventListener("ended", () => {
          if (recorderRef.current?.state === "recording") recorderRef.current.stop();
          setError("마이크 연결이 끊어져 녹음이 중단되었습니다. 다시 녹음해 주세요.");
          setStatus("FAILED");
        }, { once: true });
      });
      monitorLevel(stream);
      setStatus("READY");
    } catch (permissionError) {
      setStatus("FAILED");
      setError(microphoneErrorMessage(permissionError));
    }
  }, [monitorLevel]);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      setStatus("STOPPING");
      recorder.stop();
    }
    stopTimer();
  }, [stopTimer]);

  const start = useCallback(() => {
    const stream = streamRef.current;
    if (!stream || typeof MediaRecorder === "undefined") return;
    clearPreview();
    chunksRef.current = [];
    elapsedRef.current = 0;
    setElapsedSeconds(0);
    setError(undefined);
    const mimeType = selectMediaRecorderMime(MediaRecorder.isTypeSupported.bind(MediaRecorder));
    try {
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      });
      recorder.addEventListener("stop", () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mimeType || "audio/webm" });
        const previewUrl = URL.createObjectURL(blob);
        previewUrlRef.current = previewUrl;
        setRecording({ blob, previewUrl, durationSeconds: elapsedRef.current, mimeType: blob.type });
        setStatus("PREVIEW");
        stopTimer();
      });
      recorder.addEventListener("error", () => {
        setError("녹음이 중단되었습니다. 다시 녹음해 주세요.");
        setStatus("FAILED");
        stopTimer();
      });
      recorder.start(250);
      setStatus("RECORDING");
      timerRef.current = setInterval(() => {
        if (recorder.state !== "recording") return;
        elapsedRef.current += 1;
        setElapsedSeconds(elapsedRef.current);
        if (elapsedRef.current >= MAX_VOICE_DURATION_SECONDS) stop();
      }, 1000);
    } catch {
      setError("이 브라우저의 녹음 형식을 시작하지 못했습니다. WAV 파일을 업로드해 주세요.");
      setStatus("FAILED");
    }
  }, [clearPreview, stop, stopTimer]);

  const pause = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.pause();
      setStatus("PAUSED");
    }
  }, []);
  const resume = useCallback(() => {
    if (recorderRef.current?.state === "paused") {
      recorderRef.current.resume();
      setStatus("RECORDING");
    }
  }, []);
  const reset = useCallback(() => {
    clearPreview();
    setElapsedSeconds(0);
    elapsedRef.current = 0;
    setError(undefined);
    setStatus(streamRef.current ? "READY" : "IDLE");
  }, [clearPreview]);
  const cancel = useCallback(() => {
    if (recorderRef.current?.state !== "inactive") recorderRef.current?.stop();
    stopTimer();
    clearPreview();
    setElapsedSeconds(0);
    elapsedRef.current = 0;
    setStatus(streamRef.current ? "READY" : "IDLE");
  }, [clearPreview, stopTimer]);

  useEffect(() => () => {
    stopTimer();
    stopStream();
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
  }, [stopStream, stopTimer]);

  const levelLabel = level < 0.08 ? "낮음" : level < 0.65 ? "적정" : "높음";
  return {
    status, elapsedSeconds, level, levelLabel, error, recording,
    requestPermission, start, pause, resume, stop, reset, cancel, stopStream,
  };
}
