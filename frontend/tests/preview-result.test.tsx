import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResultPanel } from "@/features/pipeline/result-panel";
import { dohaApi } from "@/services/doha-api";
import { usePlayerStore } from "@/stores/player-store";

let previewStatus: string | undefined = "pending";
vi.mock("@/hooks/use-pipeline", () => ({
  usePipeline: () => ({ data: {
    status: "COMPLETED", prompt: "Synthetic result", duration_seconds: 30,
    result_metadata: previewStatus ? { preview: { status: previewStatus } } : {},
  } }),
}));
vi.mock("@/services/doha-api", () => ({
  dohaApi: { getPipelineFiles: vi.fn() },
}));

const preview = {
  id: "preview", job_id: "job", file_type: "preview", mime_type: "audio/wav",
  created_at: "2026-10-12T00:00:00Z", content_available: true, download_available: true,
  content_url: "/api/pipelines/job/files/preview/content",
  download_url: "/api/pipelines/job/files/preview/download",
};

describe("Preview result", () => {
  beforeEach(() => {
    previewStatus = "pending";
    vi.mocked(dohaApi.getPipelineFiles).mockReset().mockResolvedValue([]);
  });

  it("pending → ready에서 파일을 재조회하고 Player와 다운로드 URL을 재사용한다", async () => {
    const query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = () => <QueryClientProvider client={query}><ResultPanel jobId="job" /></QueryClientProvider>;
    const { rerender } = render(view());
    expect(screen.getByText("미리듣기 준비 중")).toBeInTheDocument();
    await waitFor(() => expect(dohaApi.getPipelineFiles).toHaveBeenCalledTimes(1));
    vi.mocked(dohaApi.getPipelineFiles).mockResolvedValue([preview]);
    previewStatus = "ready";
    rerender(view());
    await waitFor(() => expect(dohaApi.getPipelineFiles).toHaveBeenCalledTimes(2));
    const button = await screen.findByRole("button", { name: "미리듣기 재생" });
    button.click();
    expect(usePlayerStore.getState().currentFile?.id).toBe("preview");
    expect(screen.getByRole("link", { name: "미리듣기 WAV 다운로드" })).toHaveAttribute(
      "href", "/backend/api/pipelines/job/files/preview/download",
    );
    query.clear();
  });

  it.each(["failed", "unavailable", undefined])("%s 결과는 미리듣기 버튼을 숨긴다", (status) => {
    previewStatus = status;
    const query = new QueryClient();
    render(<QueryClientProvider client={query}><ResultPanel jobId="job" /></QueryClientProvider>);
    expect(screen.queryByRole("button", { name: "미리듣기 재생" })).not.toBeInTheDocument();
    expect(screen.getByText(status === "failed"
      ? "미리듣기를 만들지 못했습니다. 완성곡은 사용할 수 있습니다."
      : "미리듣기 미제공")).toBeInTheDocument();
    query.clear();
  });
});
