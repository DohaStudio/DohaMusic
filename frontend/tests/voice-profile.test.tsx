import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  isDevVoicePathEnabled,
  MAX_VOICE_FILE_BYTES,
  validateVoiceFile,
  VoiceProfilePanel,
} from "@/features/voice/voice-profile";
import { VoiceStep } from "@/features/studio/voice-step";
import { useStudioStore } from "@/stores/studio-store";
import type { VoiceProfileDto } from "@/types/api";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  upload: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("@/services/doha-api", () => ({
  dohaApi: {
    listVoiceProfiles: mocks.list,
    uploadVoiceProfile: mocks.upload,
    deleteVoiceProfile: mocks.remove,
    createVoiceProfile: vi.fn(),
  },
}));

const profile: VoiceProfileDto = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "내 목소리",
  display_filename: "voice.wav",
  mime_type: "audio/wav",
  size_bytes: 1000,
  duration_seconds: 8,
  sample_rate: 48000,
  channels: 1,
  consent_confirmed: true,
  consent_text_version: "v1",
  status: "READY",
  quality_warnings: ["LOW_VOLUME"],
  created_at: "2026-07-31T00:00:00Z",
  updated_at: "2026-07-31T00:00:00Z",
};

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("Voice Profile 사용자 흐름", () => {
  const originalFlag = process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH;

  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH;
    useStudioStore.getState().reset();
    mocks.list.mockResolvedValue([]);
    mocks.upload.mockResolvedValue(profile);
    mocks.remove.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
    if (originalFlag === undefined) delete process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH;
    else process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH = originalFlag;
  });

  it("기본 모드에서 upload를 제공하고 개발 경로는 숨긴다", async () => {
    renderWithQuery(<VoiceProfilePanel />);
    expect(screen.getByLabelText("목소리 파일")).toHaveAttribute("accept", expect.stringContaining(".wav"));
    expect(screen.queryByLabelText("서버 참조 파일 경로")).not.toBeInTheDocument();
    expect(await screen.findByText(/아직 등록한 목소리가 없습니다/)).toBeInTheDocument();
  });

  it("동의와 client 파일 검증 후 multipart upload하고 선택한다", async () => {
    renderWithQuery(<VoiceProfilePanel />);
    const user = userEvent.setup();
    const file = new File(["wave"], "voice.wav", { type: "audio/wav" });
    await user.type(screen.getByLabelText("빠른 등록 이름"), "내 목소리");
    await user.upload(screen.getByLabelText("목소리 파일"), file);
    expect(screen.getByRole("button", { name: "내 목소리 등록" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "내 목소리 등록" }));
    await waitFor(() => expect(mocks.upload).toHaveBeenCalled());
    expect(useStudioStore.getState().voiceProfileId).toBe(profile.id);
  });

  it("지원하지 않는 확장자와 25MB 초과를 client에서 거절한다", () => {
    expect(
      validateVoiceFile(new File(["x"], "voice.mp3", { type: "audio/mpeg" })),
    ).toBe("WAV 파일만 등록할 수 있습니다.");
    const large = new File(["x"], "large.wav", { type: "audio/wav" });
    Object.defineProperty(large, "size", { value: MAX_VOICE_FILE_BYTES + 1 });
    expect(validateVoiceFile(large)).toBe("파일은 25MB 이하여야 합니다.");
  });

  it("목록의 warning을 표시하고 선택·삭제한다", async () => {
    mocks.list.mockResolvedValue([profile]);
    renderWithQuery(<VoiceProfilePanel />);
    const user = userEvent.setup();
    expect(await screen.findByText("LOW_VOLUME")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "선택" }));
    expect(useStudioStore.getState().voiceProfileId).toBe(profile.id);
    await user.click(screen.getByRole("button", { name: "삭제" }));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith(profile.id));
  });

  it("Studio에서 목록 선택 전 다음 단계를 차단하고 선택을 저장한다", async () => {
    mocks.list.mockResolvedValue([profile]);
    renderWithQuery(<VoiceStep />);
    const user = userEvent.setup();
    const next = screen.getByRole("button", { name: "최종 확인" });
    expect(next).toBeDisabled();
    await user.click(await screen.findByRole("radio", { name: /내 목소리/ }));
    expect(next).toBeEnabled();
    expect(useStudioStore.getState().voiceProfileId).toBe(profile.id);
  });

  it("개발 플래그가 정확히 true일 때만 경로 입력을 노출한다", () => {
    expect(isDevVoicePathEnabled("true")).toBe(true);
    expect(isDevVoicePathEnabled("TRUE")).toBe(false);
    process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH = "true";
    renderWithQuery(<VoiceProfilePanel />);
    expect(screen.getByLabelText("서버 참조 파일 경로")).toBeInTheDocument();
  });
});
