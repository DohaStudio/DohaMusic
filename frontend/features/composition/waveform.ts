export const MAX_WAVEFORM_SOURCE_BYTES = 128 * 1024 * 1024;
export const MAX_WAVEFORM_PEAKS = 2048;

const MAX_SAMPLES_PER_BUCKET = 256;

export interface WaveformSource {
  cacheKey: string;
  contentUrl: string;
  mediaType: string;
  sizeBytes: number;
}

export type WaveformLoader = (
  source: WaveformSource,
  signal: AbortSignal,
) => Promise<number[]>;

interface WaveformAudioBuffer {
  length: number;
  numberOfChannels: number;
  getChannelData: (channel: number) => ArrayLike<number>;
}

export class WaveformLoadError extends Error {
  constructor(public readonly code: string) {
    super(code);
    this.name = "WaveformLoadError";
  }
}

export const loadWaveformPeaks: WaveformLoader = async (source, signal) => {
  validateWaveformSource(source);
  const response = await fetch(source.contentUrl, {
    method: "GET",
    credentials: "same-origin",
    signal,
  });
  if (!response.ok) throw new WaveformLoadError("WAVEFORM_FETCH_FAILED");

  const mediaType = response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase();
  if (!mediaType?.startsWith("audio/")) {
    throw new WaveformLoadError("WAVEFORM_MEDIA_TYPE_INVALID");
  }
  const contentLength = Number(response.headers.get("content-length"));
  if (
    !Number.isSafeInteger(contentLength)
    || contentLength <= 0
    || contentLength > MAX_WAVEFORM_SOURCE_BYTES
    || contentLength !== source.sizeBytes
  ) {
    throw new WaveformLoadError("WAVEFORM_SIZE_INVALID");
  }

  const bytes = await response.arrayBuffer();
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  if (bytes.byteLength !== contentLength) {
    throw new WaveformLoadError("WAVEFORM_SIZE_MISMATCH");
  }

  const AudioContextClass = window.AudioContext
    ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextClass) throw new WaveformLoadError("WAVEFORM_DECODE_UNAVAILABLE");

  const context = new AudioContextClass();
  try {
    const buffer = await context.decodeAudioData(bytes);
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    return buildWaveformPeaks(buffer);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    if (error instanceof WaveformLoadError) throw error;
    throw new WaveformLoadError("WAVEFORM_DECODE_FAILED");
  } finally {
    await context.close().catch(() => undefined);
  }
};

export function buildWaveformPeaks(
  buffer: WaveformAudioBuffer,
  peakLimit = MAX_WAVEFORM_PEAKS,
): number[] {
  const boundedLimit = Math.min(Math.max(Math.floor(peakLimit), 1), MAX_WAVEFORM_PEAKS);
  if (buffer.length <= 0 || buffer.numberOfChannels <= 0) return [];

  const bucketCount = Math.min(buffer.length, boundedLimit);
  const bucketSize = Math.ceil(buffer.length / bucketCount);
  const sampleStride = Math.max(1, Math.ceil(bucketSize / MAX_SAMPLES_PER_BUCKET));
  const channels = Array.from(
    { length: buffer.numberOfChannels },
    (_, channel) => buffer.getChannelData(channel),
  );
  const peaks = new Array<number>(bucketCount).fill(0);
  let maximum = 0;

  for (let bucket = 0; bucket < bucketCount; bucket += 1) {
    const start = bucket * bucketSize;
    const end = Math.min(start + bucketSize, buffer.length);
    let peak = 0;
    for (const channel of channels) {
      let sampleAccessCount = 0;
      let lastSampledIndex = -1;
      for (let sample = start; sample < end; sample += sampleStride) {
        const amplitude = Math.abs(channel[sample] ?? 0);
        sampleAccessCount += 1;
        lastSampledIndex = sample;
        if (Number.isFinite(amplitude)) peak = Math.max(peak, amplitude);
      }
      const finalSampleIndex = end - 1;
      if (
        end > start
        && lastSampledIndex !== finalSampleIndex
        && sampleAccessCount < MAX_SAMPLES_PER_BUCKET
      ) {
        const finalAmplitude = Math.abs(channel[finalSampleIndex] ?? 0);
        if (Number.isFinite(finalAmplitude)) peak = Math.max(peak, finalAmplitude);
      }
    }
    peaks[bucket] = peak;
    maximum = Math.max(maximum, peak);
  }

  if (maximum <= 0) return peaks;
  return peaks.map((peak) => peak / maximum);
}

export function buildWaveformPath(peaks: number[], width = 1000, height = 96): string {
  if (!peaks.length) return "";
  const middle = height / 2;
  const amplitude = height * 0.42;
  const x = (index: number) => (
    peaks.length === 1 ? width / 2 : (index / (peaks.length - 1)) * width
  );
  const top = peaks.map((peak, index) => `${x(index)},${middle - peak * amplitude}`);
  const bottom = peaks
    .map((peak, index) => `${x(index)},${middle + peak * amplitude}`)
    .reverse();
  return `M${top.join(" L")} L${bottom.join(" L")} Z`;
}

function validateWaveformSource(source: WaveformSource): void {
  if (
    !source.contentUrl.startsWith("/backend/api/v1/artifacts/")
    || !source.contentUrl.endsWith("/content")
    || !source.mediaType.startsWith("audio/")
  ) {
    throw new WaveformLoadError("WAVEFORM_SOURCE_INVALID");
  }
  if (
    !Number.isSafeInteger(source.sizeBytes)
    || source.sizeBytes <= 0
    || source.sizeBytes > MAX_WAVEFORM_SOURCE_BYTES
  ) {
    throw new WaveformLoadError("WAVEFORM_SOURCE_TOO_LARGE");
  }
}
