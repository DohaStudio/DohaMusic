import { expect, test, type Page, type TestInfo } from "@playwright/test";

const enrollmentId = "55555555-5555-4555-8555-555555555555";
const sampleId = "66666666-6666-4666-8666-666666666666";
const profileId = "77777777-7777-4777-8777-777777777777";

type QualityStatus = "PASS" | "WARNING" | "FAIL";

function sample(qualityStatus: QualityStatus = "PASS", warnings: string[] = []) {
  return {
    id: sampleId,
    enrollment_id: enrollmentId,
    source_type: "FILE_UPLOAD",
    prompt_id: null as string | null,
    category: "BASIC_SPEECH",
    status: qualityStatus === "FAIL" ? "FAILED" : "READY",
    original_content_type: "audio/wav",
    original_size_bytes: 192044,
    normalized_content_type: "audio/wav",
    normalized_size_bytes: 576044,
    duration_seconds: 6,
    sample_rate: 48000,
    channels: 1,
    bit_depth: 16,
    quality: {
      status: qualityStatus,
      warnings,
      version: "basic-v1",
      peak: 0.2,
      rms: 0.1,
      silence_ratio: 0,
      clipping_ratio: 0,
    },
    failure_code: qualityStatus === "FAIL" ? "VOICE_SAMPLE_VALIDATION_FAILED" : null,
    submit_eligible: qualityStatus !== "FAIL",
    cleanup_status: "NOT_REQUESTED",
    created_at: "2026-08-02T00:00:00Z",
    validated_at: "2026-08-02T00:00:01Z",
  };
}

function enrollment(
  status: "DRAFT" | "READY_TO_SUBMIT" | "COMPLETED" | "CANCELLED" = "DRAFT",
  samples: ReturnType<typeof sample>[] = [],
  cleanupStatus = "NOT_REQUESTED",
) {
  return {
    id: enrollmentId,
    status,
    name: "Validation Voice",
    description: "F6 Validation",
    consent_confirmed: true,
    consent_policy_version: "v1",
    sample_count: samples.length,
    samples,
    can_submit: status === "READY_TO_SUBMIT" && samples.some((item) => item.submit_eligible),
    validation_summary: {
      ready: samples.filter((item) => item.quality.status === "PASS").length,
      warning: samples.filter((item) => item.quality.status === "WARNING").length,
      failed: samples.filter((item) => item.quality.status === "FAIL").length,
    },
    cleanup_status: cleanupStatus,
    cleanup_failure_code: cleanupStatus === "FAILED" ? "DELETE_FAILED" : null,
    voice_profile_id: status === "COMPLETED" ? profileId : null,
    created_at: "2026-08-02T00:00:00Z",
    updated_at: "2026-08-02T00:00:01Z",
    expires_at: "2026-08-03T00:00:00Z",
    absolute_expires_at: "2026-08-09T00:00:00Z",
  };
}

const profile = {
  id: profileId,
  name: "Validation Voice",
  display_filename: null,
  mime_type: "audio/wav",
  size_bytes: 576044,
  duration_seconds: 6,
  sample_rate: 48000,
  channels: 1,
  consent_confirmed: true,
  consent_text_version: "v1",
  status: "READY",
  quality_warnings: [],
  created_at: "2026-08-02T00:00:02Z",
  updated_at: "2026-08-02T00:00:02Z",
};

async function preparePage(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("doha-studio-settings", JSON.stringify({
      state: { reducedMotion: true, onboardingCompleted: true },
      version: 0,
    }));
  });
  await page.route("**/backend/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/backend/api/voice-profiles", (route) => route.fulfill({ json: [profile] }));
}

async function openSampleStep(page: Page) {
  await page.goto("/voice");
  await page.getByRole("button", { name: "등록 시작" }).click();
  for (const checkbox of await page.getByRole("checkbox").all()) await checkbox.check();
  await page.getByRole("button", { name: "동의하고 계속" }).click();
  await page.getByLabel("목소리 이름").fill("Validation Voice");
  await page.getByLabel("설명 (선택)").fill("F6 Validation");
  await page.getByRole("button", { name: "녹음·업로드 준비" }).click();
}

async function mockCreate(page: Page, state: { current: ReturnType<typeof enrollment> }) {
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}`, (route) => route.fulfill({ json: state.current }));
  await page.route("**/backend/api/voice-enrollments", async (route) => {
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    await route.fulfill({ status: 201, json: state.current });
  });
}

function onlyChrome(testInfo: TestInfo) {
  test.skip(testInfo.project.name !== "chrome", "상세 오류 UX는 Chrome에서 대표 검증하고 브라우저 Matrix는 전체 정상 흐름으로 검증한다.");
}

test.beforeEach(async ({ page }) => preparePage(page));

test("PASS 업로드부터 대표 Sample·Profile 생성까지 브라우저 Matrix에서 완료한다", async ({ page }) => {
  const accepted = sample();
  const state = { current: enrollment() };
  await mockCreate(page, state);
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/samples`, async (route) => {
    state.current = enrollment("READY_TO_SUBMIT", [accepted]);
    await route.fulfill({ status: 201, json: accepted });
  });
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/submit`, async (route) => {
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    expect(route.request().postDataJSON().active_reference_sample_id).toBe(sampleId);
    state.current = enrollment("COMPLETED", [accepted], "COMPLETED");
    await route.fulfill({ status: 201, json: state.current });
  });

  await openSampleStep(page);
  await page.locator('input[type="file"][multiple]').setInputFiles({
    name: "validation.wav",
    mimeType: "audio/wav",
    buffer: Buffer.from("RIFFvalidationWAVE"),
  });
  await page.getByRole("button", { name: "품질 결과 확인" }).click();
  await expect(page.getByText("기본 검사를 통과했습니다.")).toBeVisible();
  await page.getByRole("button", { name: "대표 Sample 선택" }).click();
  await page.getByRole("radio", { name: /validation.wav/ }).check();
  await page.getByRole("button", { name: "프로필 확인" }).click();
  await page.getByRole("button", { name: "목소리 등록 완료" }).click();
  await expect(page.getByRole("heading", { name: "목소리 등록이 완료되었습니다" })).toBeVisible();
  await expect(page.getByText(/음악 만들기에 선택됨/)).toBeVisible();
});

for (const warning of ["LOW_VOLUME", "HIGH_SILENCE_RATIO", "POSSIBLE_CLIPPING"]) {
  test(`${warning} 경고는 확인 전 제출을 막고 확인 후 허용한다`, async ({ page }, testInfo) => {
    onlyChrome(testInfo);
    const warned = sample("WARNING", [warning]);
    const state = { current: enrollment() };
    await mockCreate(page, state);
    await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/samples`, async (route) => {
      state.current = enrollment("READY_TO_SUBMIT", [warned]);
      await route.fulfill({ status: 201, json: warned });
    });
    await openSampleStep(page);
    await page.locator('input[type="file"][multiple]').setInputFiles({
      name: `${warning}.wav`, mimeType: "audio/wav", buffer: Buffer.from("RIFFwarningWAVE"),
    });
    await page.getByRole("button", { name: "품질 결과 확인" }).click();
    const next = page.getByRole("button", { name: "대표 Sample 선택" });
    await expect(next).toBeDisabled();
    await page.getByLabel("이 Sample의 품질 경고를 확인했습니다.").check();
    await expect(next).toBeEnabled();
  });
}

const uploadErrors = [
  ["VOICE_SAMPLE_DURATION_TOO_SHORT", "음성은 5초 이상이어야 합니다."],
  ["VOICE_SAMPLE_DURATION_TOO_LONG", "음성은 60초 이하여야 합니다."],
  ["VOICE_SAMPLE_DECODE_FAILED", "음성 파일을 읽지 못했습니다."],
  ["VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE", "지원하는 WAV, WebM 또는 Ogg"],
  ["VOICE_NORMALIZER_UNAVAILABLE", "현재 서버에서는 이 녹음 형식을 처리할 수 없습니다."],
  ["REQUEST_TIMEOUT", "서버 응답이 지연되고 있습니다."],
] as const;

for (const [code, message] of uploadErrors) {
  test(`${code} 업로드 실패를 안전한 사용자 메시지로 표시한다`, async ({ page }, testInfo) => {
    onlyChrome(testInfo);
    const state = { current: enrollment() };
    await mockCreate(page, state);
    await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/samples`, (route) => route.fulfill({
      status: code === "VOICE_NORMALIZER_UNAVAILABLE" ? 503 : 422,
      json: { error: { code, message: "internal detail must not leak" } },
    }));
    await openSampleStep(page);
    await page.locator('input[type="file"][multiple]').setInputFiles({
      name: code === "VOICE_NORMALIZER_UNAVAILABLE" ? "recording.webm" : "validation.wav",
      mimeType: code === "VOICE_NORMALIZER_UNAVAILABLE" ? "audio/webm" : "audio/wav",
      buffer: Buffer.from("invalid-audio"),
    });
    await expect(page.getByText(new RegExp(message))).toBeVisible();
    await expect(page.locator("body")).not.toContainText("internal detail must not leak");
  });
}

test("지원하지 않는 확장자는 요청 전에 차단한다", async ({ page }, testInfo) => {
  onlyChrome(testInfo);
  const state = { current: enrollment() };
  let uploads = 0;
  await mockCreate(page, state);
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/samples`, (route) => {
    uploads += 1;
    return route.abort();
  });
  await openSampleStep(page);
  await page.locator('input[type="file"][multiple]').setInputFiles({
    name: "unsupported.mp3", mimeType: "audio/mpeg", buffer: Buffer.from("not-supported"),
  });
  await expect(page.getByText(/WAV, WebM 또는 Ogg 음성 파일/)).toBeVisible();
  expect(uploads).toBe(0);
});

test("중복 업로드 재시도는 동일 Idempotency-Key를 사용한다", async ({ page }, testInfo) => {
  onlyChrome(testInfo);
  const accepted = sample();
  const state = { current: enrollment() };
  const keys: string[] = [];
  let attempts = 0;
  await mockCreate(page, state);
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/samples`, async (route) => {
    attempts += 1;
    keys.push(route.request().headers()["idempotency-key"]);
    if (attempts === 1) {
      await route.fulfill({ status: 503, json: { error: { code: "NETWORK_ERROR", message: "retry" } } });
      return;
    }
    state.current = enrollment("READY_TO_SUBMIT", [accepted]);
    await route.fulfill({ status: 201, json: accepted });
  });
  await openSampleStep(page);
  await page.locator('input[type="file"][multiple]').setInputFiles({
    name: "retry.wav", mimeType: "audio/wav", buffer: Buffer.from("RIFFretryWAVE"),
  });
  await page.getByRole("button", { name: "업로드 재시도" }).click();
  await expect(page.getByText("1/10 Sample")).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]);
});

test("제출 버튼 중복 조작은 동일 Idempotency-Key로 하나의 Profile에 수렴한다", async ({ page }, testInfo) => {
  onlyChrome(testInfo);
  const accepted = sample();
  const state = { current: enrollment() };
  let submits = 0;
  const submitKeys: string[] = [];
  await mockCreate(page, state);
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/samples`, async (route) => {
    state.current = enrollment("READY_TO_SUBMIT", [accepted]);
    await route.fulfill({ status: 201, json: accepted });
  });
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/submit`, async (route) => {
    submits += 1;
    submitKeys.push(route.request().headers()["idempotency-key"]);
    await new Promise((resolve) => setTimeout(resolve, 100));
    state.current = enrollment("COMPLETED", [accepted], "COMPLETED");
    await route.fulfill({ status: 201, json: state.current });
  });
  await openSampleStep(page);
  await page.locator('input[type="file"][multiple]').setInputFiles({
    name: "submit.wav", mimeType: "audio/wav", buffer: Buffer.from("RIFFsubmitWAVE"),
  });
  await page.getByRole("button", { name: "품질 결과 확인" }).click();
  await page.getByRole("button", { name: "대표 Sample 선택" }).click();
  await page.getByRole("radio", { name: /submit.wav/ }).check();
  await page.getByRole("button", { name: "프로필 확인" }).click();
  const submit = page.getByRole("button", { name: "목소리 등록 완료" });
  await submit.dblclick();
  await expect(page.getByRole("heading", { name: "목소리 등록이 완료되었습니다" })).toBeVisible();
  expect(submits).toBe(2);
  expect(new Set(submitKeys).size).toBe(1);
});

test("취소 후 cleanup pending 상태와 새 등록 복귀를 표시한다", async ({ page }, testInfo) => {
  onlyChrome(testInfo);
  const state = { current: enrollment() };
  await mockCreate(page, state);
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/cancel`, (route) => route.fulfill({
    json: enrollment("CANCELLED", [], "PENDING"),
  }));
  page.on("dialog", (dialog) => dialog.accept());
  await openSampleStep(page);
  await page.getByRole("button", { name: "등록 취소" }).click();
  await expect(page.getByText("등록은 취소됐고 임시 음성 파일을 삭제하는 중입니다.")).toBeVisible();
  await expect(page.getByRole("button", { name: "등록 시작" })).toBeVisible();
});

test("MediaRecorder가 생성한 Blob을 preview한 뒤 업로드한다", async ({ page }, testInfo) => {
  onlyChrome(testInfo);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => {
          const context = new AudioContext();
          const oscillator = context.createOscillator();
          const destination = context.createMediaStreamDestination();
          oscillator.connect(destination);
          oscillator.start();
          return destination.stream;
        },
      },
    });
  });
  const recorded = { ...sample(), source_type: "BROWSER_RECORDING", prompt_id: "ko_speech_neutral_01" };
  const state = { current: enrollment() };
  let sourceType = "";
  let uploadedType = "";
  await mockCreate(page, state);
  await page.route(`**/backend/api/voice-enrollments/${enrollmentId}/samples`, async (route) => {
    const multipart = await route.request().postDataBuffer();
    const body = multipart?.toString("latin1") ?? "";
    sourceType = body.includes("BROWSER_RECORDING") ? "BROWSER_RECORDING" : "";
    uploadedType = route.request().headers()["content-type"] ?? "";
    state.current = enrollment("READY_TO_SUBMIT", [recorded]);
    await route.fulfill({ status: 201, json: recorded });
  });
  await openSampleStep(page);
  await page.getByRole("button", { name: "마이크 권한 요청" }).click();
  await page.getByRole("button", { name: "녹음 시작" }).click();
  await expect(page.getByText("00:05")).toBeVisible({ timeout: 7_000 });
  await page.getByRole("button", { name: "녹음 종료" }).click();
  await expect(page.locator(".enrollment-step audio")).toBeVisible();
  await page.getByRole("button", { name: "이 녹음 업로드" }).click();
  await expect(page.getByText("1/10 Sample")).toBeVisible();
  expect(sourceType).toBe("BROWSER_RECORDING");
  expect(uploadedType).toContain("multipart/form-data");
});

test("MediaRecorder MIME 지원과 실제 Blob type을 기록한다", async ({ page }, testInfo) => {
  await page.goto("/voice");
  const result = await page.evaluate(async () => {
    const candidates = [
      "audio/wav",
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg",
      "audio/mp4",
    ];
    if (typeof MediaRecorder === "undefined") {
      return { available: false, supported: {}, recorderMimeType: null, blobType: null };
    }
    const supported = Object.fromEntries(candidates.map((mime) => [mime, MediaRecorder.isTypeSupported(mime)]));
    const context = new AudioContext();
    const oscillator = context.createOscillator();
    const destination = context.createMediaStreamDestination();
    oscillator.connect(destination);
    oscillator.start();
    const preferred = candidates.find((mime) => supported[mime]);
    const recorder = preferred
      ? new MediaRecorder(destination.stream, { mimeType: preferred })
      : new MediaRecorder(destination.stream);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    const stopped = new Promise<void>((resolve) => { recorder.onstop = () => resolve(); });
    recorder.start(50);
    await new Promise((resolve) => setTimeout(resolve, 180));
    recorder.stop();
    await stopped;
    oscillator.stop();
    await context.close();
    return { available: true, supported, recorderMimeType: recorder.mimeType, blobType: new Blob(chunks, { type: recorder.mimeType }).type };
  });
  console.log(`VOICE_MIME_PROBE ${testInfo.project.name} ${JSON.stringify(result)}`);
  await testInfo.attach(`mime-${testInfo.project.name}.json`, {
    body: Buffer.from(JSON.stringify(result, null, 2)), contentType: "application/json",
  });
  if (result.available) expect(result.blobType).toBeTruthy();
  else expect(testInfo.project.name).toBe("iphone-14");
});
