import { test, expect, type Page } from "@playwright/test";
const uuid = "11111111-1111-1111-1111-111111111111";
const pipeline = {
  id: "job-001",
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
          content_available: false,
          download_available: false,
          created_at: "2026-07-31T00:00:01Z",
        },
      ],
    }),
  );
}
test("Landing에서 결과 metadata까지 핵심 흐름을 완료한다", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /당신의 이야기가/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: /첫 곡 만들기/ }).click();
  await page.getByLabel("음악 설명").fill("새벽 도시 R&B");
  await page.getByLabel("길이 (초)").fill("45");
  await page.getByRole("button", { name: "가사 단계로" }).click();
  await page.getByLabel("가사").fill("[Verse]\n빛나는 거리");
  await page.getByRole("button", { name: "가사 검증" }).click();
  await expect(page.getByText("검증을 통과했습니다.")).toBeVisible();
  await page.getByRole("button", { name: "목소리 선택" }).click();
  await page.getByLabel("Voice Profile UUID").fill(uuid);
  await page.getByRole("button", { name: "생성 확인" }).click();
  await expect(page.getByText("45초")).toBeVisible();
  await page.getByRole("button", { name: "음악 생성 시작" }).click();
  await expect(page).toHaveURL(/\/result\/job-001/);
  await expect(
    page.getByRole("heading", { name: "결과 Metadata" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /다운로드/ })).toBeDisabled();
  await expect(page.getByText("C:/internal/final.wav")).toHaveCount(0);
});
test("미지원 Voice upload는 반응형 화면에서 disabled다", async ({
  page,
}, testInfo) => {
  await mockBackend(page);
  await page.goto("/voice");
  await expect(
    page.getByRole("button", { name: /음성 파일 업로드/ }),
  ).toBeDisabled();
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
  await page.getByRole("button", { name: "가사 생성" }).click();

  await expect(page.getByText("의미 기반 수정 미지원")).toBeVisible();
  await expect(page.getByLabel("수정 지시")).toHaveCount(0);
});

test("네트워크 오류에서도 Job ID를 보존하고 수동 재조회를 제공한다", async ({
  page,
}) => {
  await page.route("**/backend/api/pipelines/network-job", (route) =>
    route.abort("failed"),
  );

  await page.goto("/generation/network-job");

  await expect(page.getByText("Backend 연결이 불안정합니다")).toBeVisible();
  await expect(page.getByText(/Job은 취소되지 않았습니다/)).toBeVisible();
  await expect(page.getByRole("button", { name: "수동 재조회" })).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/\/generation\/network-job/);
});
