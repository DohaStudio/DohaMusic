import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ValidationResult } from "@/features/lyrics/lyrics-lab";
import { Unsupported } from "@/components/ui";
import { StepIndicator } from "@/components/step-indicator";
import { CancelDialog } from "@/features/pipeline/cancel-dialog";
describe("Frontend components", () => {
  it("Lyrics warning과 error를 구분한다", () => {
    render(
      <ValidationResult
        value={{
          valid: false,
          normalized_lyrics: "",
          sections: [],
          warnings: ["반복 주의"],
          errors: ["섹션 오류"],
          character_count: 0,
          line_count: 0,
          section_count: 0,
          repetition_ratio: 0,
        }}
      />,
    );
    expect(screen.getByText("오류 · 섹션 오류")).toBeInTheDocument();
    expect(screen.getByText("주의 · 반복 주의")).toBeInTheDocument();
  });
  it("취소 Dialog는 안전한 동작에 초점을 두고 Esc와 확인을 지원한다", async () => {
    const close = vi.fn(); const confirm = vi.fn(); const user = userEvent.setup();
    render(<CancelDialog open pending={false} onClose={close} onConfirm={confirm} />);
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "계속 만들기" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "취소하기" }));
    expect(confirm).toHaveBeenCalledOnce();
    await user.keyboard("{Escape}");
    expect(close).toHaveBeenCalledOnce();
  });
  it("Backend Required control은 비활성이다", () => {
    render(<Unsupported>업로드</Unsupported>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
  it("모바일에서도 사용되는 step에 aria-current를 표시한다", () => {
    render(<StepIndicator current="voice" />);
    expect(screen.getByText("내 목소리").closest("li")).toHaveAttribute(
      "aria-current",
      "step",
    );
  });
});
