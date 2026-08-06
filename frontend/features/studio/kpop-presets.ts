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
  defaultOptions: Omit<KPopGenerationOptions, "presetId" | "hook">;
}

export type KPopHookStyle = "title_repeat" | "chant";
export type KPopVocalEnergy = "low" | "medium" | "high";
export interface KPopGenerationOptions {
  presetId: KPopPresetId;
  requestedBpm: number;
  languageRatio: { ko: number; en: number };
  hook?: { phrase: string; style: KPopHookStyle; repeatCount: number };
  includePostChorus: boolean;
  includeDanceBreak: boolean;
  vocalEnergy: KPopVocalEnergy;
  concept?: string;
}

export const KPOP_PROMPT_COMPILER_VERSION = "kpop-prompt-v1";
export const DEFAULT_KPOP_PRESET_ID: KPopPresetId = "kpop_dance";
export const KPOP_GENERATION_CAPABILITIES = {
  presetId: "prompt_compiled",
  requestedBpm: "prompt_compiled",
  languageRatio: "prompt_compiled",
  hook: "prompt_compiled",
  includePostChorus: "prompt_compiled",
  includeDanceBreak: "prompt_compiled",
  vocalEnergy: "prompt_compiled",
  concept: "prompt_compiled",
  detectedBpm: "not_supported",
  hookTimestamp: "not_supported",
  audioAnalysis: "not_supported",
} as const;

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
    defaultOptions: {
      requestedBpm: 124,
      languageRatio: { ko: 70, en: 30 },
      includePostChorus: true,
      includeDanceBreak: false,
      vocalEnergy: "medium",
      concept: "confident_bright",
    },
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
    defaultOptions: {
      requestedBpm: 104,
      languageRatio: { ko: 80, en: 20 },
      includePostChorus: true,
      includeDanceBreak: false,
      vocalEnergy: "low",
      concept: "warm_fresh",
    },
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
    defaultOptions: {
      requestedBpm: 142,
      languageRatio: { ko: 60, en: 40 },
      includePostChorus: true,
      includeDanceBreak: true,
      vocalEnergy: "high",
      concept: "bold_performance",
    },
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

export function createDefaultKPopGenerationOptions(
  presetId: KPopPresetId,
): KPopGenerationOptions {
  const preset = getKPopPreset(presetId);
  return {
    presetId,
    ...preset.defaultOptions,
    languageRatio: { ...preset.defaultOptions.languageRatio },
  };
}

export function validateKPopGenerationOptions(
  options: KPopGenerationOptions,
): void {
  if (!Number.isInteger(options.requestedBpm) || options.requestedBpm < 70 || options.requestedBpm > 180) {
    throw new Error("목표 BPM은 70에서 180 사이의 정수여야 합니다.");
  }
  const { ko, en } = options.languageRatio;
  if (![ko, en].every((value) => Number.isInteger(value) && value >= 0 && value <= 100) || ko + en !== 100) {
    throw new Error("한국어와 영어 비율의 합은 100이어야 합니다.");
  }
  if (options.hook) {
    const phrase = normalize(options.hook.phrase);
    if (!phrase || phrase.length > 40) throw new Error("후렴 Hook은 1~40자로 입력해 주세요.");
    if (!Number.isInteger(options.hook.repeatCount) || options.hook.repeatCount < 1 || options.hook.repeatCount > 6) {
      throw new Error("Hook 반복 횟수는 1에서 6 사이여야 합니다.");
    }
  }
  if (options.concept && normalize(options.concept).length > 40) {
    throw new Error("곡 콘셉트는 40자 이내로 입력해 주세요.");
  }
}

export function withKPopCustomDirections(
  options: KPopGenerationOptions,
  directions: readonly string[],
): KPopGenerationOptions {
  const concepts = [options.concept ?? "", ...directions]
    .map(normalize)
    .filter((value, index, values) => value && values.indexOf(value) === index);
  const concept = concepts.join(", ");
  const merged = { ...options, concept: concept || undefined };
  validateKPopGenerationOptions(merged);
  return merged;
}

export function compileKPopPrompt(input: {
  presetId: KPopPresetId;
  userPrompt: string;
  customPrompt?: string;
  options?: KPopGenerationOptions;
}): KPopCompilationResult {
  const preset = getKPopPreset(input.presetId);
  const userPrompt = normalize(input.userPrompt);
  const customPrompt = normalize(input.customPrompt ?? "");
  rejectArtistImitation(userPrompt);
  rejectArtistImitation(customPrompt);
  if (input.options) validateKPopGenerationOptions(input.options);

  const sections = [
    "Create an original modern Korean pop song.",
    "Preset direction (use only when it does not conflict with user input):",
    preset.defaultPrompt,
    `Preset mood: ${preset.defaultMood}. Preset energy: ${preset.defaultEnergy}.`,
  ];
  if (input.options) {
    const options = input.options;
    sections.push(
      "Structured user options (override preset defaults):",
      `Target tempo around ${options.requestedBpm} BPM; treat this as a prompt goal, not an exact guarantee.`,
      `Lyrics language target: ${options.languageRatio.ko}% Korean and ${options.languageRatio.en}% English; do not claim an exact final ratio.`,
    );
    if (options.hook) {
      const style = options.hook.style === "title_repeat" ? "a repeated title hook" : "a chant-style hook";
      sections.push(
        `Include ${style}: "${normalize(options.hook.phrase)}".`,
        `Repeat the hook approximately ${options.hook.repeatCount} times.`,
      );
    }
    sections.push(
      options.includePostChorus ? "Include a post-chorus." : "Do not include a post-chorus.",
      options.includeDanceBreak ? "Include a dance-break contrast." : "Do not include a dance break.",
      `Use ${options.vocalEnergy} vocal energy.`,
    );
    if (options.concept) sections.push(`Concept: ${normalize(options.concept)}.`);
  }
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
