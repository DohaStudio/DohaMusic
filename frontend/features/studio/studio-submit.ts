import type { PipelineCreateDto } from "@/types/api";

export interface PipelineDraftInput {
  prompt: string;
  lyricsText: string;
  genre: string;
  selectedMoods?: string[];
  durationSeconds: number;
  seed?: number;
  voiceProfileId: string;
}
export function toPipelineCreate(input: PipelineDraftInput): PipelineCreateDto {
  return {
    prompt: [input.prompt, input.selectedMoods?.length ? `분위기: ${input.selectedMoods.join(", ")}` : ""]
      .filter(Boolean)
      .join("\n"),
    lyrics: input.lyricsText || undefined,
    genre: input.genre || undefined,
    duration_seconds: input.durationSeconds,
    seed: input.seed,
    voice_profile_id: input.voiceProfileId,
  };
}
