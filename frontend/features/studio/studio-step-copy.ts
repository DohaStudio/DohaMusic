import type { StudioStep } from "@/types/domain";

export const studioStepCopy: Record<
  StudioStep,
  { title: string; subtitle: string }
> = {
  settings: {
    title: "어떤 음악을 만들까요?",
    subtitle: "장르와 분위기를 선택하면 가사부터 목소리 적용까지 단계별로 도와드립니다.",
  },
  lyrics: {
    title: "이야기에 가사를 입혀요",
    subtitle: "직접 쓰거나 가사 만들기에서 준비한 내용을 사용하세요.",
  },
  voice: {
    title: "노래할 목소리를 연결해요",
    subtitle: "본인 또는 사용 동의를 받은 목소리만 선택할 수 있습니다.",
  },
  review: {
    title: "생성 설정을 확인해요",
    subtitle: "음악 스타일, 가사, 내 목소리와 곡 길이를 확인해 주세요.",
  },
  generation: {
    title: "음악을 만들고 있어요",
    subtitle: "완료될 때까지 이 화면을 유지해 주세요.",
  },
  result: {
    title: "결과가 준비됐어요",
    subtitle: "완성된 음악을 듣고 저장할 수 있습니다.",
  },
};
