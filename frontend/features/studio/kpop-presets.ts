export type KPopPresetId =
  | "kpop_dance"
  | "kpop_easy_listening"
  | "kpop_performance";

export interface PresetDefinition {
  id: KPopPresetId;
  displayName: string;
  description: string;
  genre: string;
  defaultPrompt: string;
  defaultMood: string;
  defaultEnergy: "medium" | "high";
}

export const KPOP_PROMPT_COMPILER_VERSION = "kpop-prompt-v1";
export const DEFAULT_KPOP_PRESET_ID: KPopPresetId = "kpop_dance";

export const KPOP_PRESETS: readonly PresetDefinition[] = [
  {
    id: "kpop_dance",
    displayName: "K-POP Dance",
    description: "밝고 세련된 리듬과 힘 있는 후렴을 중심으로 한 댄스 팝",
    genre: "kpop_dance",
    defaultPrompt:
      "Modern Korean dance pop with bright polished synth layers, rhythmic electronic drums, a rising pre-chorus, and an energetic chorus with clear Korean pronunciation.",
    defaultMood: "bright, confident",
    defaultEnergy: "high",
  },
  {
    id: "kpop_easy_listening",
    displayName: "K-POP Easy Listening",
    description: "따뜻하고 편안한 질감과 자연스러운 반복을 살린 소프트 팝",
    genre: "kpop_easy_listening",
    defaultPrompt:
      "Soft modern Korean pop with warm synth textures, restrained drums, a smooth song structure, a comfortable repeated chorus, and a close natural vocal delivery.",
    defaultMood: "warm, fresh",
    defaultEnergy: "medium",
  },
  {
    id: "kpop_performance",
    displayName: "K-POP Performance",
    description: "강한 대비와 무대 에너지를 강조한 퍼포먼스 팝",
    genre: "kpop_performance",
    defaultPrompt:
      "High-energy Korean performance pop with bold electronic bass, strong rhythmic drums, a tense rising pre-chorus, a chant-like hook, and a powerful chorus.",
    defaultMood: "bold, intense",
    defaultEnergy: "high",
  },
] as const;

const artistImitationPatterns = [
  /\bin\s+the\s+style\s+of\b/i,
  /\bsound(?:ing)?\s+like\b/i,
  /\bimitat(?:e|ing)\b.{0,40}\b(?:artist|singer|voice)\b/i,
  /(?:가수|아티스트|아이돌).{0,30}(?:처럼|같이|스타일|문체|창법)/,
  /\S+\s*(?:처럼|같이)\s*(?:노래|불러|목소리|창법)/,
];

export function getKPopPreset(id: KPopPresetId): PresetDefinition {
  const preset = KPOP_PRESETS.find((candidate) => candidate.id === id);
  if (!preset) throw new Error(`Unsupported K-POP preset: ${id}`);
  return preset;
}

function normalize(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function rejectArtistImitation(value: string): void {
  if (artistImitationPatterns.some((pattern) => pattern.test(value))) {
    throw new Error("특정 아티스트의 스타일·문체·창법 모방은 지원하지 않습니다.");
  }
}

export interface KPopCompilationResult {
  prompt: string;
  genre: string;
  presetId: KPopPresetId;
  compilerVersion: string;
}

export function compileKPopPrompt(input: {
  presetId: KPopPresetId;
  userPrompt: string;
  customPrompt?: string;
}): KPopCompilationResult {
  const preset = getKPopPreset(input.presetId);
  const userPrompt = normalize(input.userPrompt);
  const customPrompt = normalize(input.customPrompt ?? "");
  rejectArtistImitation(userPrompt);
  rejectArtistImitation(customPrompt);

  const sections = [
    "Create an original modern Korean pop song.",
    "Preset direction (use only when it does not conflict with user input):",
    preset.defaultPrompt,
    `Preset mood: ${preset.defaultMood}. Preset energy: ${preset.defaultEnergy}.`,
  ];
  if (customPrompt) sections.push("Additional user direction:", customPrompt);
  if (userPrompt) {
    sections.push(
      "User request (highest priority; follow this when directions conflict):",
      userPrompt,
    );
  }
  const prompt = sections.join("\n\n");
  if (prompt.length > 1500) {
    throw new Error("K-POP Prompt는 컴파일 후 1,500자 이하여야 합니다.");
  }
  return {
    prompt,
    genre: preset.genre,
    presetId: preset.id,
    compilerVersion: KPOP_PROMPT_COMPILER_VERSION,
  };
}
