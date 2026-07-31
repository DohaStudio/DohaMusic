import type { PipelineCreateDto } from "@/types/api";

export interface PipelineDraftInput {
  prompt: string;
  lyricsText: string;
  genre: string;
  durationSeconds: number;
  seed?: number;
  voiceProfileId: string;
}
export function toPipelineCreate(input: PipelineDraftInput): PipelineCreateDto {
  return {
    prompt: input.prompt,
    lyrics: input.lyricsText || undefined,
    genre: input.genre || undefined,
    duration_seconds: input.durationSeconds,
    seed: input.seed,
    voice_profile_id: input.voiceProfileId,
  };
}
