import type { LyricsSectionDto, PipelineStatus } from "./api";

export type StudioStep =
  | "settings"
  | "lyrics"
  | "voice"
  | "review"
  | "generation"
  | "result";
export interface SafePipelineFile {
  id: string;
  jobId: string;
  fileType: string;
  mimeType: string;
  createdAt: string;
  contentAvailable: boolean;
  downloadAvailable: boolean;
  contentUrl?: string;
  downloadUrl?: string;
}
export interface LyricsView {
  id: string;
  title: string;
  fullText: string;
  sections: LyricsSectionDto[];
  providerLabel: string;
  modelLabel: string;
  version: number;
}
export interface PipelineStageView {
  status: PipelineStatus;
  label: string;
  tone: "neutral" | "active" | "success" | "error";
}
