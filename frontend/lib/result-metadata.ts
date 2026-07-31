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
  pushGenerationOptions(rows, metadata.generation_options);
  if (typeof metadata.kpop_prompt_compiler_version === "string") {
    rows.push({ label: "K-POP Compiler", value: metadata.kpop_prompt_compiler_version });
  }
  return rows;
}

function pushGenerationOptions(rows: PublicMetadataRow[], value: unknown): void {
  if (!isRecord(value)) return;
  const presetLabels: Readonly<Record<string, string>> = {
    kpop_dance: "K-POP Dance",
    kpop_easy_listening: "K-POP Easy Listening",
    kpop_performance: "K-POP Performance",
  };
  if (typeof value.preset_id === "string" && presetLabels[value.preset_id]) {
    rows.push({ label: "K-POP 스타일", value: presetLabels[value.preset_id] });
  }
  pushNumber(rows, "목표 BPM", value.requested_bpm, " BPM (Prompt 목표)");
  if (isRecord(value.language_ratio) && typeof value.language_ratio.ko === "number" && typeof value.language_ratio.en === "number") {
    rows.push({ label: "가사 언어 목표", value: `한국어 ${value.language_ratio.ko}% · 영어 ${value.language_ratio.en}%` });
  }
  if (isRecord(value.hook) && typeof value.hook.phrase === "string") {
    rows.push({ label: "후렴 Hook", value: value.hook.phrase });
  }
  if (typeof value.vocal_energy === "string") rows.push({ label: "보컬 에너지", value: value.vocal_energy });
  if (typeof value.concept === "string") rows.push({ label: "콘셉트", value: value.concept });
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
