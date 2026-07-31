import type { StudioStep } from "@/types/domain";

export const studioStepCopy: Record<
  StudioStep,
  { title: string; subtitle: string }
> = {
  settings: {
    title: "어떤 음악을 만들까요?",
    subtitle: "지원되는 Pipeline 필드만으로 첫 곡을 설계합니다.",
  },
  lyrics: {
    title: "이야기에 가사를 입혀요",
    subtitle: "직접 쓰거나 Lyrics Lab 결과를 이어서 사용하세요.",
  },
  voice: {
    title: "노래할 목소리를 연결해요",
    subtitle: "동의된 Voice Profile만 사용할 수 있습니다.",
  },
  review: {
    title: "생성 설정을 확인해요",
    subtitle: "확인 후 하나의 추적 가능한 Job으로 생성합니다.",
  },
  generation: {
    title: "음악을 만들고 있어요",
    subtitle: "Job URL에서 진행 상태를 복원합니다.",
  },
  result: {
    title: "결과가 준비됐어요",
    subtitle: "공개 가능한 metadata만 표시합니다.",
  },
};
