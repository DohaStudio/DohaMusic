import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildWaveformPath,
  buildWaveformPeaks,
  loadWaveformPeaks,
  MAX_WAVEFORM_PEAKS,
  MAX_WAVEFORM_SOURCE_BYTES,
} from "@/features/composition/waveform";

function audioBuffer(channels: Float32Array[]) {
  return {
    length: channels[0]?.length ?? 0,
    numberOfChannels: channels.length,
    getChannelData: (channel: number) => channels[channel],
  };
}

function instrumentedChannel(length: number, amplitudeAt = -1) {
  const accessedIndexes: number[] = [];
  const channel = new Proxy({ length } as ArrayLike<number>, {
    get(target, property, receiver) {
      if (typeof property === "string" && /^\d+$/.test(property)) {
        const index = Number(property);
        accessedIndexes.push(index);
        return index === amplitudeAt ? 1 : 0;
      }
      return Reflect.get(target, property, receiver);
    },
  });
  return { channel, accessedIndexes };
}

describe("Waveform peak foundation", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("긴 audio sample을 bounded peak로 downsample하고 정규화한다", () => {
    const samples = new Float32Array(100_000);
    samples[50_000] = 0.8;
    samples[99_999] = -0.4;
    const peaks = buildWaveformPeaks(audioBuffer([samples]), 64);
    expect(peaks).toHaveLength(64);
    expect(Math.max(...peaks)).toBe(1);
    expect(peaks.every((peak) => peak >= 0 && peak <= 1)).toBe(true);
  });

  it("256 sample bucket에서 channel element 접근을 256회 이하로 제한한다", () => {
    const measured = instrumentedChannel(256, 255);
    expect(buildWaveformPeaks({
      length: 256,
      numberOfChannels: 1,
      getChannelData: () => measured.channel,
    }, 1)).toEqual([1]);
    expect(measured.accessedIndexes).toHaveLength(256);
  });

  it.each([0, 1, 2, 255, 256, 257, 512, 1_000_000])(
    "bucketSize=%i에서 channel element 접근 상한을 지킨다",
    (bucketSize) => {
      const measured = instrumentedChannel(bucketSize);
      buildWaveformPeaks({
        length: bucketSize,
        numberOfChannels: 1,
        getChannelData: () => measured.channel,
      }, 1);
      expect(measured.accessedIndexes.length).toBeLessThanOrEqual(256);
    },
  );

  it("접근 예산이 남아 있을 때만 마지막 sample을 peak에 포함한다", () => {
    const measured = instrumentedChannel(258, 257);
    expect(buildWaveformPeaks({
      length: 258,
      numberOfChannels: 1,
      getChannelData: () => measured.channel,
    }, 1)).toEqual([1]);
    expect(measured.accessedIndexes).toContain(257);
    expect(measured.accessedIndexes.length).toBeLessThanOrEqual(256);
  });

  it("exact boundary와 partial final bucket 각각의 접근 상한을 지킨다", () => {
    const exact = instrumentedChannel(512);
    buildWaveformPeaks({
      length: 512,
      numberOfChannels: 1,
      getChannelData: () => exact.channel,
    }, 2);
    expect(exact.accessedIndexes.filter((index) => index < 256)).toHaveLength(256);
    expect(exact.accessedIndexes.filter((index) => index >= 256)).toHaveLength(256);

    const partial = instrumentedChannel(515);
    buildWaveformPeaks({
      length: 515,
      numberOfChannels: 1,
      getChannelData: () => partial.channel,
    }, 2);
    expect(partial.accessedIndexes.filter((index) => index < 258).length).toBeLessThanOrEqual(256);
    expect(partial.accessedIndexes.filter((index) => index >= 258).length).toBeLessThanOrEqual(256);
  });

  it("각 channel에 독립적으로 bucket 접근 상한을 적용한다", () => {
    const left = instrumentedChannel(512);
    const right = instrumentedChannel(512);
    buildWaveformPeaks({
      length: 512,
      numberOfChannels: 2,
      getChannelData: (channel) => channel === 0 ? left.channel : right.channel,
    }, 1);
    expect(left.accessedIndexes.length).toBeLessThanOrEqual(256);
    expect(right.accessedIndexes.length).toBeLessThanOrEqual(256);
  });

  it("NaN과 Infinity를 peak에 포함하지 않고 normalized range를 유지한다", () => {
    const peaks = buildWaveformPeaks(audioBuffer([
      new Float32Array([Number.NaN, Number.POSITIVE_INFINITY, -0.5]),
    ]));
    expect(peaks).toEqual([0, 0, 1]);
    expect(peaks.every(Number.isFinite)).toBe(true);
  });

  it("호출자가 큰 limit을 요청해도 peak와 SVG DOM path를 bounded하게 유지한다", () => {
    const peaks = buildWaveformPeaks(audioBuffer([new Float32Array(10_000)]), 10_000);
    expect(peaks.length).toBeLessThanOrEqual(MAX_WAVEFORM_PEAKS);
    expect(buildWaveformPath([0.2, 1, 0.4])).toMatch(/^M.+Z$/);
  });

  it("Content-Length와 metadata size를 검증한 safe Artifact만 decode한다", async () => {
    const bytes = new Uint8Array([1, 2, 3, 4]).buffer;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(bytes, {
      status: 200,
      headers: { "Content-Type": "audio/wav", "Content-Length": "4" },
    })));
    const close = vi.fn().mockResolvedValue(undefined);
    const decodeAudioData = vi.fn().mockResolvedValue(audioBuffer([
      new Float32Array([0, 0.5, -1, 0.25]),
    ]));
    vi.stubGlobal("AudioContext", class {
      decodeAudioData = decodeAudioData;
      close = close;
    });

    const peaks = await loadWaveformPeaks({
      cacheKey: "artifact:checksum",
      contentUrl: "/backend/api/v1/artifacts/artifact/content",
      mediaType: "audio/wav",
      sizeBytes: 4,
    }, new AbortController().signal);

    expect(peaks).toEqual([0, 0.5, 1, 0.25]);
    expect(fetch).toHaveBeenCalledWith(
      "/backend/api/v1/artifacts/artifact/content",
      expect.objectContaining({ credentials: "same-origin" }),
    );
    expect(decodeAudioData).toHaveBeenCalledTimes(1);
    expect(close).toHaveBeenCalledTimes(1);
  });

  it("무제한 source와 외부 URL은 fetch 전에 fail-closed한다", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(loadWaveformPeaks({
      cacheKey: "large",
      contentUrl: "/backend/api/v1/artifacts/artifact/content",
      mediaType: "audio/wav",
      sizeBytes: MAX_WAVEFORM_SOURCE_BYTES + 1,
    }, new AbortController().signal)).rejects.toMatchObject({
      code: "WAVEFORM_SOURCE_TOO_LARGE",
    });
    await expect(loadWaveformPeaks({
      cacheKey: "external",
      contentUrl: "https://example.com/audio.wav",
      mediaType: "audio/wav",
      sizeBytes: 4,
    }, new AbortController().signal)).rejects.toMatchObject({
      code: "WAVEFORM_SOURCE_INVALID",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
