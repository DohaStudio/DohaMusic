import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VoiceEnrollmentWizard } from "@/features/voice/voice-enrollment-wizard";

const mocks = vi.hoisted(() => ({
  create: vi.fn(), get: vi.fn(), upload: vi.fn(), remove: vi.fn(), submit: vi.fn(), cancel: vi.fn(),
}));

vi.mock("@/services/doha-api", () => ({
  dohaApi: {
    createVoiceEnrollment: mocks.create,
    getVoiceEnrollment: mocks.get,
    uploadVoiceEnrollmentSample: mocks.upload,
    deleteVoiceEnrollmentSample: mocks.remove,
    submitVoiceEnrollment: mocks.submit,
    cancelVoiceEnrollment: mocks.cancel,
  },
}));

const draft = {
  id: "11111111-1111-4111-8111-111111111111",
  status: "DRAFT" as const,
  name: "내 목소리",
  description: "테스트",
  consent_confirmed: true,
  consent_policy_version: "v1",
  sample_count: 0,
  samples: [],
  can_submit: false,
  validation_summary: { ready: 0, warning: 0, failed: 0 },
  cleanup_status: "NOT_REQUESTED",
  cleanup_failure_code: null,
  voice_profile_id: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  expires_at: "2026-08-02T00:00:00Z",
  absolute_expires_at: "2026-08-08T00:00:00Z",
};

function renderWizard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><VoiceEnrollmentWizard /></QueryClientProvider>);
}

describe("Guided Voice Enrollment Wizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.create.mockResolvedValue(draft);
    mocks.get.mockResolvedValue(draft);
    mocks.cancel.mockResolvedValue({ ...draft, status: "CANCELLED", cleanup_status: "COMPLETED" });
  });

  it("안내 단계에서 안전·품질 한계와 WAV fallback을 표시한다", async () => {
    renderWizard();
    expect(await screen.findByText("권리와 개인정보")).toBeInTheDocument();
    expect(screen.getByText(/최종 변환 품질을 보장하지 않습니다/)).toBeInTheDocument();
    expect(screen.getByText(/WAV 파일 업로드/)).toBeInTheDocument();
  });

  it("필수 동의 전에는 다음 단계 진행을 차단한다", async () => {
    renderWizard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "등록 시작" }));
    expect(screen.getByRole("button", { name: "동의하고 계속" })).toBeDisabled();
    const checks = screen.getAllByRole("checkbox");
    for (const check of checks) await user.click(check);
    expect(screen.getByRole("button", { name: "동의하고 계속" })).toBeEnabled();
  });

  it("프로필 정보와 동의를 실제 create API에 전달하고 Sample 단계로 이동한다", async () => {
    renderWizard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "등록 시작" }));
    for (const check of screen.getAllByRole("checkbox")) await user.click(check);
    await user.click(screen.getByRole("button", { name: "동의하고 계속" }));
    await user.type(screen.getByLabelText("목소리 이름"), "내 목소리");
    await user.type(screen.getByLabelText("설명 (선택)"), "테스트");
    await user.click(screen.getByRole("button", { name: "녹음·업로드 준비" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({
      name: "내 목소리", consent_confirmed: true, consent_policy_version: "v1",
    }), expect.any(String)));
    expect(await screen.findByText("기존 파일 추가")).toBeInTheDocument();
    expect(sessionStorage.getItem("doha.voice-enrollment.v1")).toContain(draft.id);
  });

  it("sessionStorage ID로 업로드 완료 상태를 다시 조회한다", async () => {
    sessionStorage.setItem("doha.voice-enrollment.v1", JSON.stringify({ enrollmentId: draft.id, step: "samples" }));
    renderWizard();
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(draft.id, expect.any(AbortSignal)));
    expect(await screen.findByText("기존 파일 추가")).toBeInTheDocument();
  });
});
