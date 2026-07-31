import { test, expect, type Page } from "@playwright/test";
const uuid = "11111111-1111-1111-1111-111111111111";
const voiceProfile = {
  id: uuid,
  name: "Doha Voice",
  display_filename: "voice-reference.wav",
  mime_type: "audio/wav",
  size_bytes: 320044,
  duration_seconds: 10,
  sample_rate: 16000,
  channels: 1,
  consent_confirmed: true,
  consent_text_version: "v1",
  status: "READY",
  quality_warnings: [],
  created_at: "2026-07-31T00:00:00Z",
  updated_at: "2026-07-31T00:00:00Z",
};
const pipeline = {
  id: "job-001",
  project_id: "project-001",
  voice_profile_id: uuid,
  status: "COMPLETED",
  current_step: "completed",
  progress_percent: 100,
  prompt: "새벽 도시 R&B",
  lyrics: "[Verse]\n빛나는 거리",
  genre: "R&B",
  duration_seconds: 30,
  seed: null,
  pipeline_version: "mock-v1",
  result_metadata: { provider: "mock", sample_rate: 48000 },
  failed_step: null,
  error_code: null,
  error_message: null,
  created_at: "2026-07-31T00:00:00Z",
  updated_at: "2026-07-31T00:00:01Z",
  completed_at: "2026-07-31T00:00:01Z",
};
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("doha-studio-settings", JSON.stringify({ state: { reducedMotion: null, onboardingCompleted: true }, version: 0 })));
});
async function mockBackend(page: Page) {
  await page.route("**/backend/health", (r) =>
    r.fulfill({ json: { status: "ok" } }),
  );
  await page.route("**/backend/api/lyrics/validate", (r) =>
    r.fulfill({
      json: {
        valid: true,
        normalized_lyrics: "",
        sections: [],
        warnings: [],
        errors: [],
        character_count: 10,
        line_count: 2,
        section_count: 1,
        repetition_ratio: 0,
      },
    }),
  );
  await page.route("**/backend/api/voice-profiles", (route) =>
    route.fulfill({ json: [voiceProfile] }),
  );
  await page.route("**/backend/api/voice-profiles/upload", (route) =>
    route.fulfill({ status: 201, json: voiceProfile }),
  );
  await page.route("**/backend/api/pipelines", (r) =>
    r.fulfill({ status: 202, json: pipeline }),
  );
  await page.route("**/backend/api/pipelines/job-001", (r) =>
    r.fulfill({ json: pipeline }),
  );
  await page.route("**/backend/api/pipelines/job-001/files", (r) =>
    r.fulfill({
      json: [
        {
          id: "file-1",
          job_id: "job-001",
          file_type: "final",
          mime_type: "audio/wav",
          content_available: true,
          download_available: true,
          content_url: "/api/pipelines/job-001/files/file-1/content",
          download_url: "/api/pipelines/job-001/files/file-1/download",
          created_at: "2026-07-31T00:00:01Z",
        },
      ],
    }),
  );
  await page.route("**/backend/api/pipelines/job-001/files/file-1/content", (r) =>
    r.fulfill({ status: 200, contentType: "audio/wav", body: "RIFFmockWAVE" }),
  );
  await page.route("**/backend/api/pipelines/job-001/files/file-1/download", (r) =>
    r.fulfill({
      status: 200,
      contentType: "audio/wav",
      headers: { "Content-Disposition": 'attachment; filename="doha-job-final.wav"' },
      body: "RIFFmockWAVE",
    }),
  );
  await page.route("**/backend/api/history**", (route) =>
    route.fulfill({ json: [{ job_id: "job-001", project_id: "project-001", title: "새벽 도시 R&B", status: "COMPLETED", created_at: pipeline.created_at, duration: 30, voice_profile_name: "Doha Voice", has_audio: true }] }),
  );
  await page.route("**/backend/api/projects", (route) =>
    route.fulfill({ json: [{ id: "project-001", title: "Default Project", description: null, created_at: pipeline.created_at, updated_at: pipeline.updated_at, job_count: 1 }] }),
  );
}
test("History에서 Result와 Player로 다시 이동한다", async ({ page }) => {
  await page.addInitScript(() => { HTMLMediaElement.prototype.play = async function () { this.dispatchEvent(new Event("play")); }; });
  await mockBackend(page);
  await page.goto("/history");
  await expect(page.getByRole("heading", { name: "새벽 도시 R&B" })).toBeVisible();
  await page.locator(".history-row").getByRole("button", { name: "재생" }).click();
  await expect(page.locator("audio")).toHaveAttribute("src", "/backend/api/pipelines/job-001/files/file-1/content");
  await page.getByRole("link", { name: "자세히 보기" }).click();
  await expect(page).toHaveURL(/\/result\/job-001/);
  await expect(page.getByRole("link", { name: "WAV 다운로드" })).toBeVisible();
});
test("Landing에서 결과 metadata까지 핵심 흐름을 완료한다", async ({ page }) => {
  await page.addInitScript(() => {
    HTMLMediaElement.prototype.play = async function () {
      this.dispatchEvent(new Event("play"));
    };
    HTMLMediaElement.prototype.pause = function () {
      this.dispatchEvent(new Event("pause"));
    };
  });
  await mockBackend(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /당신의 이야기가/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: /첫 곡 만들기/ }).click();
  await page.getByLabel("노래 설명").fill("새벽 도시 R&B");
  await page.getByRole("button", { name: /1절 중심/ }).click();
  await page.getByRole("button", { name: "가사 준비하기" }).click();
  await page.getByRole("textbox", { name: "가사" }).fill("[Verse]\n빛나는 거리");
  await page.getByRole("button", { name: "작성 내용 확인" }).click();
  await expect(page.getByText("가사 구성을 확인했습니다.")).toBeVisible();
  await page.getByRole("button", { name: "내 목소리 선택" }).click();
  await page.getByRole("radio", { name: /Doha Voice/ }).click();
  await page.getByRole("button", { name: "최종 확인" }).click();
  await expect(page.getByText("60초")).toBeVisible();
  await page.getByRole("button", { name: "음악 만들기" }).click();
  await expect(page).toHaveURL(/\/result\/job-001/);
  await expect(
    page.getByRole("heading", { name: "완성 정보" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "WAV 다운로드" }),
  ).toHaveAttribute(
    "href",
    "/backend/api/pipelines/job-001/files/file-1/download",
  );
  await expect(page.locator("audio")).toHaveAttribute(
    "src",
    "/backend/api/pipelines/job-001/files/file-1/content",
  );
  await page.locator(".result-hero").getByRole("button", { name: "재생" }).click();
  const resultPause = page.locator(".result-hero").getByRole("button", {
    name: "일시정지",
  });
  await expect(resultPause).toBeVisible();
  await resultPause.click();
  await expect(
    page.locator(".result-hero").getByRole("button", { name: "재생" }),
  ).toBeVisible();
  await expect(page.getByText("C:/internal/final.wav")).toHaveCount(0);
});
test("Voice WAV를 등록하고 목록에서 선택한다", async ({
  page,
}, testInfo) => {
  await mockBackend(page);
  await page.goto("/voice");
  await page.getByLabel("목소리 이름").fill("Doha Voice");
  await page.getByLabel("목소리 파일").setInputFiles({
    name: "voice-reference.wav",
    mimeType: "audio/wav",
    buffer: Buffer.from("RIFFmock-dataWAVE"),
  });
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "내 목소리 등록" }).click();
  await expect(page.getByText("Doha Voice").first()).toBeVisible();
  await expect(page.getByText(/음악 만들기에 선택됨/)).toBeVisible();
  await expect(page.getByLabel("서버 참조 파일 경로")).toHaveCount(0);
  if (testInfo.project.name === "mobile") {
    await expect(
      page.getByRole("navigation", { name: "모바일 메뉴" }),
    ).toBeVisible();
  } else {
    await expect(
      page.getByRole("navigation", { name: "주요 메뉴" }),
    ).toBeVisible();
  }
});

test("Template 가사는 의미 기반 revision을 활성화하지 않는다", async ({
  page,
}) => {
  await mockBackend(page);
  await page.route("**/backend/api/lyrics", (route) =>
    route.fulfill({
      status: 201,
      json: {
        id: "lyrics-1",
        parent_id: null,
        version: 1,
        revision_instruction: null,
        source_hash: null,
        result_hash: null,
        title: "Template 가사",
        language: "ko",
        topic: "밤",
        genre: "R&B",
        mood: "따뜻한",
        keywords: [],
        structure: ["verse", "chorus"],
        sections: [],
        full_text: "[Verse]\n빛나는 거리",
        provider: "template",
        model_name: "template",
        model_version: null,
        status: "GENERATED",
        metadata: { capabilities: { revision: false } },
        created_at: "2026-07-31T00:00:00Z",
        updated_at: "2026-07-31T00:00:00Z",
      },
    }),
  );

  await page.goto("/lyrics");
  await page.getByLabel("주제").fill("밤");
  await page.getByRole("button", { name: "가사 만들어보기" }).click();

  await expect(page.getByText(/AI에게 다시 고쳐달라고 요청하는 기능은 준비 중/)).toBeVisible();
  await expect(page.getByLabel("수정 지시")).toHaveCount(0);
});

test("네트워크 오류에서도 Job ID를 보존하고 수동 재조회를 제공한다", async ({
  page,
}) => {
  await page.route("**/backend/api/pipelines/network-job", (route) =>
    route.abort("failed"),
  );

  await page.goto("/generation/network-job");

  await expect(page.getByText("진행 상태를 불러오지 못했습니다")).toBeVisible();
  await expect(page.getByText("음악 생성 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 확인" })).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/\/generation\/network-job/);
});
