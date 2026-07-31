import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GlobalPlayer } from "@/features/player/global-player";
import { selectPreferredAudioFile } from "@/lib/mappers";
import {
  getPipelineFileContentUrl,
  getPipelineFileDownloadUrl,
  toBackendPublicUrl,
} from "@/services/doha-api";
import { usePlayerStore } from "@/stores/player-store";
import type { SafePipelineFile } from "@/types/domain";

const file = (type: string, available = true): SafePipelineFile => ({
  id: `${type}-id`,
  jobId: "job/id",
  fileType: type,
  mimeType: "audio/wav",
  createdAt: "2026-07-31T00:00:00Z",
  contentAvailable: available,
  downloadAvailable: available,
  contentUrl: available ? `/backend/content/${type}` : undefined,
  downloadUrl: available ? `/backend/download/${type}` : undefined,
});

describe("Audio Player", () => {
  beforeEach(() => {
    usePlayerStore.getState().reset();
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  });

  it("final부터 실제 file type 우선순위로 선택한다", () => {
    expect(
      selectPreferredAudioFile([
        file("music"),
        file("instrumental"),
        file("final"),
      ])?.fileType,
    ).toBe("final");
    expect(selectPreferredAudioFile([file("final", false)])).toBeUndefined();
  });

  it("same-origin content와 download URL을 안전하게 생성한다", () => {
    expect(getPipelineFileContentUrl("job/id", "file id")).toBe(
      "/backend/api/pipelines/job%2Fid/files/file%20id/content",
    );
    expect(getPipelineFileDownloadUrl("job/id", "file id")).toBe(
      "/backend/api/pipelines/job%2Fid/files/file%20id/download",
    );
    expect(toBackendPublicUrl("/api/pipelines/job/files/file/content")).toBe(
      "/backend/api/pipelines/job/files/file/content",
    );
    expect(toBackendPublicUrl("https://example.com/secret")).toBeUndefined();
  });

  it("선택 전 비활성이고 선택 후 play·pause·seek·volume을 제어한다", async () => {
    const user = userEvent.setup();
    const { container } = render(<GlobalPlayer />);
    expect(screen.getByRole("button", { name: "재생" })).toBeDisabled();

    act(() => usePlayerStore.getState().select(file("final")));
    await user.click(screen.getByRole("button", { name: "재생" }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled();

    const audio = container.querySelector("audio")!;
    Object.defineProperty(audio, "duration", { value: 30, configurable: true });
    fireEvent.loadedMetadata(audio);
    const seek = screen.getByLabelText("재생 위치");
    fireEvent.change(seek, { target: { value: "12" } });
    expect(audio.currentTime).toBe(12);

    const volume = screen.getByLabelText("볼륨");
    fireEvent.change(volume, { target: { value: "0.4" } });
    expect(audio.volume).toBe(0.4);

    await user.click(screen.getByRole("button", { name: "일시정지" }));
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled();
  });

  it("media 오류를 사용자에게 표시한다", () => {
    const { container } = render(<GlobalPlayer />);
    act(() => usePlayerStore.getState().select(file("final")));
    fireEvent.error(container.querySelector("audio")!);
    expect(
      screen.getByText("오디오를 불러오지 못했습니다."),
    ).toBeInTheDocument();
  });
});
