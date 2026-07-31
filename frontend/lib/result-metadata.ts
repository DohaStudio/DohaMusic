export interface PublicMetadataRow {
  label: string;
  value: string;
}

const providerLabels: Readonly<Record<string, string>> = {
  music: "음악 생성 Provider",
  stem: "음원 분리 Provider",
  voice: "음색 변환 Provider",
  mixer: "믹싱 Provider",
  export: "출력 Provider",
};

export function publicMetadataRows(metadata: unknown): PublicMetadataRow[] {
  if (!isRecord(metadata)) return [];
  const rows: PublicMetadataRow[] = [];

  pushSeconds(rows, "생성 길이", metadata.duration_seconds);
  pushSeconds(rows, "전체 처리 시간", metadata.execution_time_seconds);
  pushProviders(rows, metadata.providers);
  pushAudioQuality(rows, metadata.step_execution);
  return rows;
}

function pushProviders(rows: PublicMetadataRow[], value: unknown): void {
  if (!isRecord(value)) return;
  for (const [key, label] of Object.entries(providerLabels)) {
    const details = value[key];
    if (!isRecord(details) || typeof details.provider !== "string") continue;
    const provider = details.provider.trim();
    if (provider) rows.push({ label, value: provider });
  }
}

function pushAudioQuality(rows: PublicMetadataRow[], value: unknown): void {
  if (!Array.isArray(value)) return;
  const mixer = value.find(
    (item) => isRecord(item) && item.step === "mixer" && item.status === "COMPLETED",
  );
  if (!isRecord(mixer) || !isRecord(mixer.audio_quality)) return;
  const quality = mixer.audio_quality;

  pushNumber(rows, "샘플레이트", quality.sample_rate, " Hz");
  pushNumber(rows, "채널", quality.channels);
  pushNumber(rows, "Peak", quality.peak_dbfs, " dBFS");
  pushNumber(rows, "RMS", quality.rms_dbfs, " dBFS");
  pushNumber(rows, "실제 Headroom", quality.headroom_actual_db, " dB");
  if (isRecord(quality.clipping) && typeof quality.clipping.detected === "boolean") {
    rows.push({
      label: "Clipping",
      value: quality.clipping.detected ? "감지됨" : "없음",
    });
  }
}

function pushSeconds(
  rows: PublicMetadataRow[],
  label: string,
  value: unknown,
): void {
  pushNumber(rows, label, value, "초");
}

function pushNumber(
  rows: PublicMetadataRow[],
  label: string,
  value: unknown,
  suffix = "",
): void {
  if (typeof value !== "number" || !Number.isFinite(value)) return;
  rows.push({ label, value: `${value}${suffix}` });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
