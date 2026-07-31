import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  isDevVoicePathEnabled,
  VoiceProfilePanel,
} from "@/features/voice/voice-profile";
import { useStudioStore } from "@/stores/studio-store";

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <VoiceProfilePanel />
    </QueryClientProvider>,
  );
}

describe("Voice Profile 보안 경계", () => {
  const originalFlag = process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH;

  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH;
    useStudioStore.getState().reset();
  });

  afterEach(() => {
    if (originalFlag === undefined) {
      delete process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH;
    } else {
      process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH = originalFlag;
    }
  });

  it("일반 모드에서는 UUID 연결만 제공한다", () => {
    renderPanel();

    expect(screen.getByLabelText("기존 Profile UUID")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /음성 파일 업로드/ }),
    ).toBeDisabled();
    expect(
      screen.queryByLabelText("서버 참조 파일 경로"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/본인 음성 또는 명시적 동의/),
    ).not.toBeInTheDocument();
  });

  it("개발 플래그가 정확히 true일 때만 경로 입력을 노출한다", () => {
    expect(isDevVoicePathEnabled("true")).toBe(true);
    expect(isDevVoicePathEnabled("TRUE")).toBe(false);
    expect(isDevVoicePathEnabled(undefined)).toBe(false);

    process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH = "true";
    renderPanel();

    expect(screen.getByLabelText("서버 참조 파일 경로")).toBeInTheDocument();
    expect(screen.getByText("개발 전용")).toBeInTheDocument();
  });

  it("개발 모드에서도 동의 전에는 생성 요청을 막는다", async () => {
    process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH = "true";
    renderPanel();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Profile 이름"), "내 목소리");
    await user.type(
      screen.getByLabelText("서버 참조 파일 경로"),
      "voices/references/mine.wav",
    );

    expect(
      screen.getByRole("button", { name: "개발용 Profile 생성" }),
    ).toBeDisabled();
  });
});
