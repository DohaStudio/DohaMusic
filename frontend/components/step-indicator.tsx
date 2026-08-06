import type { StudioStep } from "@/types/domain";
const steps: { id: StudioStep; label: string }[] = [
  { id: "settings", label: "음악 스타일" },
  { id: "lyrics", label: "가사" },
  { id: "voice", label: "내 목소리" },
  { id: "review", label: "최종 확인" },
  { id: "generation", label: "음악 만드는 중" },
  { id: "result", label: "완성" },
];
export function StepIndicator({ current }: { current: StudioStep }) {
  const at = steps.findIndex((step) => step.id === current);
  return (
    <ol className="step-indicator" aria-label={`음악 만들기 ${at + 1}/${steps.length} 단계`}>
      {steps.map((step, index) => (
        <li
          key={step.id}
          className={index === at ? "current" : index < at ? "done" : ""}
          aria-current={index === at ? "step" : undefined}
        >
          <span>{index + 1}</span>
          <b>{step.label}</b>
        </li>
      ))}
    </ol>
  );
}
