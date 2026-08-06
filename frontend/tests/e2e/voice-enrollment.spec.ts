import { expect, test, type Page } from "@playwright/test";

const enrollmentId = "22222222-2222-4222-8222-222222222222";
const sampleId = "33333333-3333-4333-8333-333333333333";
const profileId = "44444444-4444-4444-8444-444444444444";

const sample = {
  id: sampleId,
  enrollment_id: enrollmentId,
  source_type: "FILE_UPLOAD",
  prompt_id: null,
  category: "BASIC_SPEECH",
  status: "READY",
  original_content_type: "audio/wav",
  original_size_bytes: 192044,
  normalized_content_type: "audio/wav",
  normalized_size_bytes: 576044,
  duration_seconds: 6,
  sample_rate: 48000,
  channels: 1,
  bit_depth: 16,
  quality: { status: "PASS", warnings: [], version: "basic-v1", peak: .2, rms: .1, silence_ratio: 0, clipping_ratio: 0 },
  failure_code: null,
  submit_eligible: true,
  cleanup_status: "NOT_REQUESTED",
  created_at: "2026-08-01T00:00:00Z",
  validated_at: "2026-08-01T00:00:01Z",
};

function enrollment(status: "DRAFT" | "READY_TO_SUBMIT" | "COMPLETED", samples = status === "DRAFT" ? [] : [sample]) {
  return {
    id: enrollmentId, status, name: "Guided Voice", description: "E2E",
    consent_confirmed: true, consent_policy_version: "v1",
    sample_count: samples.length, samples,
    can_submit: status === "READY_TO_SUBMIT",
    validation_summary: { ready: samples.length, warning: 0, failed: 0 },
    cleanup_status: status === "COMPLETED" ? "COMPLETED" : "NOT_REQUESTED",
    cleanup_failure_code: null,
    voice_profile_id: status === "COMPLETED" ? profileId : null,
    created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:01Z",
    expires_at: "2026-08-02T00:00:00Z", absolute_expires_at: "2026-08-08T00:00:00Z",
  };
}

const profile = {
  id: profileId, name: "Guided Voice", display_filename: null, mime_type: "audio/wav",
  size_bytes: 576044, duration_seconds: 6, sample_rate: 48000, channels: 1,
  consent_confirmed: true, consent_text_version: "v1", status: "READY", quality_warnings: [],
  created_at: "2026-08-01T00:00:02Z", updated_at: "2026-08-01T00:00:02Z",
};

async function mockEnrollmentBackend(page: Page) {
  let state = enrollment("DRAFT");
  let completed = false;
  await page.route("**/backend/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/backend/api/voice-profiles", (route) => route.fulfill({ json: completed ? [profile] : [] }));
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/samples`, async (route) => {
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    state = enrollment("READY_TO_SUBMIT");
    await route.fulfill({ status: 201, json: sample });
  });
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/submit`, async (route) => {
    const body = route.request().postDataJSON();
    expect(body.active_reference_sample_id).toBe(sampleId);
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    state = enrollment("COMPLETED");
    completed = true;
    await route.fulfill({ status: 201, json: state });
  });
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}`, (route) => route.fulfill({ json: state }));
  await page.route("**/backend/api/voice-enrollments", async (route) => {
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    await route.fulfill({ status: 201, json: state });
  });
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("doha-studio-settings", JSON.stringify({ state: { reducedMotion: true, onboardingCompleted: true }, version: 0 })));
});

test("WAV Sample 등록부터 대표 선택·Profile 생성까지 완료한다", async ({ page }, testInfo) => {
  await mockEnrollmentBackend(page);
  await page.goto("/voice");
  await page.getByRole("button", { name: "등록 시작" }).click();
  for (const checkbox of await page.getByRole("checkbox").all()) await checkbox.check();
  await page.getByRole("button", { name: "동의하고 계속" }).click();
  await page.getByLabel("목소리 이름").fill("Guided Voice");
  await page.getByLabel("설명 (선택)").fill("E2E");
  await page.getByRole("radio", { name: /기존 음성 파일 업로드/ }).check();
  await page.getByRole("button", { name: "녹음·업로드 준비" }).click();
  await page.locator('input[type="file"][multiple]').setInputFiles({
    name: "synthetic.wav", mimeType: "audio/wav", buffer: Buffer.from("RIFFsyntheticWAVE"),
  });
  await expect(page.getByText("1/10 Sample")).toBeVisible();
  await expect(page.getByText("4 / 8")).toBeVisible();
  await expect(page.getByRole("complementary", { name: "현재 음성 등록 요약" })).toContainText("1 / 10");
  await expect(page.getByRole("article", { name: "synthetic.wav, 품질 PASS" })).toBeVisible();
  if (process.env.VOICE_UI_SCREENSHOT) await page.screenshot({ path: testInfo.outputPath("samples.png"), fullPage: true });
  await page.getByRole("button", { name: "품질 결과 확인" }).click();
  await expect(page.getByText("기본 검사를 통과했습니다.")).toBeVisible();
  await page.getByRole("button", { name: "대표 Sample 선택" }).click();
  await page.getByRole("radio", { name: /synthetic.wav/ }).check();
  await page.getByRole("button", { name: "프로필 확인" }).click();
  await page.getByRole("button", { name: "목소리 등록 완료" }).click();
  await expect(page.getByRole("heading", { name: "목소리 등록이 완료되었습니다" })).toBeVisible();
  await expect(page.getByText("Guided Voice").last()).toBeVisible();
  await expect(page.getByText(/음악 만들기에 선택됨/)).toBeVisible();
  await expect(page.getByText("대표 Sample")).toBeVisible();
  if (process.env.VOICE_UI_SCREENSHOT) await page.screenshot({ path: testInfo.outputPath("complete.png"), fullPage: true });
  expect(await page.evaluate(() => sessionStorage.getItem("doha.voice-enrollment.v1"))).toBeNull();
  await expect(page.locator("body")).not.toContainText("Idempotency-Key");
  await expect(page.locator("body")).not.toContainText("storage_original_key");
  if (testInfo.project.name === "mobile") {
    await expect(page.getByRole("navigation", { name: "모바일 메뉴" })).toBeVisible();
  }
});

test("만료된 복원 ID를 제거하고 새 등록 안내를 표시한다", async ({ page }) => {
  await page.addInitScript((id) => sessionStorage.setItem("doha.voice-enrollment.v1", JSON.stringify({ enrollmentId: id, step: "samples" })), enrollmentId);
  await page.route("**/backend/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/backend/api/voice-profiles", (route) => route.fulfill({ json: [] }));
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}`, (route) => route.fulfill({ status: 410, json: { error: { code: "VOICE_ENROLLMENT_EXPIRED", message: "expired" } } }));
  await page.goto("/voice");
  await expect(page.getByText("음성 등록 시간이 만료되었습니다. 새 등록을 시작해 주세요.")).toBeVisible();
  await expect(page.getByRole("button", { name: "등록 시작" })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem("doha.voice-enrollment.v1"))).toBeNull();
});
