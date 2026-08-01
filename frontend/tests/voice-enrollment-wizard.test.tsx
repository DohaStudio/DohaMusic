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

const readySample = {
  id: "22222222-2222-4222-8222-222222222222",
  enrollment_id: draft.id,
  source_type: "FILE_UPLOAD" as const,
  prompt_id: null,
  category: "BASIC_SPEECH",
  status: "READY" as const,
  original_content_type: "audio/wav",
  original_size_bytes: 120_000,
  normalized_content_type: "audio/wav",
  normalized_size_bytes: 280_000,
  duration_seconds: 7,
  sample_rate: 48_000,
  channels: 1,
  bit_depth: 16,
  quality: { status: "PASS" as const, warnings: [], version: "basic-v1", peak: .2, rms: .1, silence_ratio: 0, clipping_ratio: 0 },
  failure_code: null,
  submit_eligible: true,
  cleanup_status: "NOT_REQUESTED",
  created_at: "2026-08-02T00:00:00Z",
  validated_at: "2026-08-02T00:00:01Z",
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
    expect(screen.getByRole("note", { name: "녹음 형식 안내" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("1 / 8")).toBeInTheDocument();
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
    expect(screen.getByText("4 / 8")).toBeInTheDocument();
    expect(screen.getByText("아직 등록된 Sample이 없습니다.")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "현재 음성 등록 요약" })).toHaveTextContent("0 / 10");
    expect(sessionStorage.getItem("doha.voice-enrollment.v1")).toContain(draft.id);
  });

  it("sessionStorage ID로 업로드 완료 상태를 다시 조회한다", async () => {
    sessionStorage.setItem("doha.voice-enrollment.v1", JSON.stringify({ enrollmentId: draft.id, step: "samples" }));
    renderWizard();
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(draft.id, expect.any(AbortSignal)));
    expect(await screen.findByText("기존 파일 추가")).toBeInTheDocument();
  });

  it("등록한 Sample을 품질·길이·대표 선택이 있는 카드와 Summary로 표시한다", async () => {
    const ready = {
      ...draft,
      status: "READY_TO_SUBMIT" as const,
      sample_count: 1,
      samples: [readySample],
      can_submit: true,
      validation_summary: { ready: 1, warning: 0, failed: 0 },
    };
    mocks.get.mockResolvedValue(ready);
    sessionStorage.setItem("doha.voice-enrollment.v1", JSON.stringify({ enrollmentId: draft.id, step: "samples" }));
    renderWizard();
    expect(await screen.findByRole("article", { name: "Sample 1, 품질 PASS" })).toBeInTheDocument();
    expect(screen.getByText("7.0초")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /대표로 선택/ })).toHaveAttribute("aria-pressed", "false");
    const summary = screen.getByRole("complementary", { name: "현재 음성 등록 요약" });
    expect(summary).toHaveTextContent("1 / 10");
    expect(summary).toHaveTextContent("PASS1");
  });
});
