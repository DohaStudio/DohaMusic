import { z } from "zod";

export const musicSettingsSchema = z.object({
  prompt: z.string().min(1, "곡의 설명을 입력해 주세요.").max(4000),
  genre: z.string().max(100),
  durationSeconds: z.number().int().min(1).max(600),
  seed: z
    .union([z.number().int().min(0).max(2147483647), z.literal("")])
    .optional(),
});
export type MusicSettingsValues = z.infer<typeof musicSettingsSchema>;
