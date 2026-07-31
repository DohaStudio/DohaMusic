"use client";

import { useStudioStore } from "@/stores/studio-store";

const help = {
  settings: { title: "댄스곡을 만들고 싶다면", items: ["장르: 댄스 팝", "분위기: 신나는·당당한", "구성: 중독성 있는 후렴"] },
  lyrics: { title: "좋은 댄스곡 가사 팁", items: ["한 문장은 짧게 작성하세요.", "후렴은 반복적으로 구성하세요.", "짧은 영어 Hook을 섞을 수 있습니다."] },
  voice: { title: "더 좋은 결과를 위한 녹음 팁", items: ["배경음악 없이 녹음하세요.", "조용한 공간을 사용하세요.", "마이크 거리를 일정하게 유지하세요."] },
  review: { title: "생성 전에 확인하세요", items: ["음악 스타일", "가사", "선택한 내 목소리", "곡 길이"] },
  generation: { title: "음악을 만들고 있습니다", items: ["음악 생성", "목소리 적용", "최종 음량 조정"] },
  result: { title: "완성된 음악", items: ["바로 듣기", "WAV로 저장", "만든 음악에서 다시 열기"] },
};

export function StudioHelp() {
  const step = useStudioStore((state) => state.currentStep);
  const content = help[step];
  return <details className="studio-help" open><summary>현재 단계 도움말</summary><h2>{content.title}</h2><ul>{content.items.map((item) => <li key={item}>{item}</li>)}</ul>{step === "generation" && <p>세부 단계는 서버에서 확인된 상태만 표시합니다. 완료될 때까지 이 화면을 유지해 주세요.</p>}</details>;
}
