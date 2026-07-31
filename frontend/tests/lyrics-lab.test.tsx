import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LyricsLab } from "@/features/lyrics/lyrics-lab";
import { ApiError } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import type { LyricsDocumentDto } from "@/types/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const templateLyrics: LyricsDocumentDto = {
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
  created_at: "",
  updated_at: "",
};

function renderLab() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <LyricsLab />
    </QueryClientProvider>,
  );
}

describe("Lyrics Lab 오류와 capability", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("삭제 실패 시 문서를 유지하고 안전한 오류를 표시한다", async () => {
    vi.spyOn(dohaApi, "createLyrics").mockResolvedValue(templateLyrics);
    vi.spyOn(dohaApi, "deleteLyrics").mockRejectedValue(
      new ApiError(503, "BACKEND_UNAVAILABLE", "삭제할 수 없습니다."),
    );
    const user = userEvent.setup();
    renderLab();

    await user.type(screen.getByLabelText("주제"), "밤");
    await user.click(screen.getByRole("button", { name: "가사 만들어보기" }));
    await screen.findByText("Template 가사");
    await user.click(screen.getByRole("button", { name: "삭제" }));

    await waitFor(() =>
      expect(screen.getByText("삭제할 수 없습니다.")).toBeInTheDocument(),
    );
    expect(screen.getByText("Template 가사")).toBeInTheDocument();
  });
});
