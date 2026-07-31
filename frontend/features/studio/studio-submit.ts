import type { PipelineCreateDto } from "@/types/api";
import {
  validateKPopGenerationOptions,
  withKPopCustomDirections,
  type KPopGenerationOptions,
  type KPopPresetId,
} from "./kpop-presets";

export interface PipelineDraftInput {
  prompt: string;
  kpopPresetId: KPopPresetId;
  lyricsText: string;
  genre: string;
  selectedMoods?: string[];
  generationOptions: KPopGenerationOptions;
  durationSeconds: number;
  seed?: number;
  voiceProfileId: string;
}
export function toPipelineCreate(input: PipelineDraftInput): PipelineCreateDto {
  const options = withKPopCustomDirections(input.generationOptions, [
    input.genre,
    ...(input.selectedMoods ?? []),
  ]);
  validateKPopGenerationOptions(options);
  return {
    prompt: input.prompt,
    lyrics: input.lyricsText || undefined,
    genre: input.kpopPresetId,
    duration_seconds: input.durationSeconds,
    seed: input.seed,
    voice_profile_id: input.voiceProfileId,
    generation_options: {
      preset_id: input.kpopPresetId,
      requested_bpm: options.requestedBpm,
      language_ratio: { ...options.languageRatio },
      hook: options.hook
        ? {
            phrase: options.hook.phrase.trim(),
            style: options.hook.style,
            repeat_count: options.hook.repeatCount,
          }
        : undefined,
      include_post_chorus: options.includePostChorus,
      include_dance_break: options.includeDanceBreak,
      vocal_energy: options.vocalEnergy,
      concept: options.concept?.trim() || undefined,
    },
  };
}
