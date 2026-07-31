import type { KPopGenerationOptionsDto } from "@/types/api";
import { getKPopPreset } from "@/features/studio/kpop-presets";

export function GenerationOptionsSummary({
  options,
  retryOfJobId,
}: {
  options?: KPopGenerationOptionsDto | null;
  retryOfJobId?: string | null;
}) {
  if (!options && !retryOfJobId) return null;
  const preset = options ? getKPopPreset(options.preset_id) : null;
  const parts = [
    preset?.displayName,
    options?.requested_bpm ? `${options.requested_bpm} BPM 목표` : undefined,
    options?.hook?.phrase ? `Hook: ${options.hook.phrase}` : undefined,
    options?.vocal_energy ? `보컬 ${options.vocal_energy}` : undefined,
    options?.concept ? `콘셉트 ${options.concept}` : undefined,
    retryOfJobId ? "다시 만든 작업" : undefined,
  ].filter(Boolean);
  return <p className="generation-options-summary">{parts.join(" · ")}</p>;
}
