import type { PipelineCreateDto } from "@/types/api";
import {
  compileKPopPrompt,
  type KPopPresetId,
} from "./kpop-presets";

export interface PipelineDraftInput {
  prompt: string;
  kpopPresetId: KPopPresetId;
  lyricsText: string;
  genre: string;
  selectedMoods?: string[];
  durationSeconds: number;
  seed?: number;
  voiceProfileId: string;
}
export function toPipelineCreate(input: PipelineDraftInput): PipelineCreateDto {
  const customPrompt = [
    input.genre ? `Additional genre direction: ${input.genre}` : "",
    input.selectedMoods?.length
      ? `Mood: ${input.selectedMoods.join(", ")}`
      : "",
  ]
    .filter(Boolean)
    .join("\n");
  const compiled = compileKPopPrompt({
    presetId: input.kpopPresetId,
    userPrompt: input.prompt,
    customPrompt,
  });
  return {
    prompt: compiled.prompt,
    lyrics: input.lyricsText || undefined,
    genre: compiled.genre,
    duration_seconds: input.durationSeconds,
    seed: input.seed,
    voice_profile_id: input.voiceProfileId,
  };
}
