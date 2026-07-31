import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest, normalizeApiError } from "@/services/api-client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
describe("API client", () => {
  it("Backend 오류 코드와 메시지를 보존한다", () => {
    const error = normalizeApiError(404, {
      error: { code: "RESOURCE_NOT_FOUND", message: "없습니다." },
    });
    expect(error).toMatchObject({
      status: 404,
      code: "RESOURCE_NOT_FOUND",
      message: "없습니다.",
    });
  });
  it("성공 응답의 깨진 JSON을 INVALID_RESPONSE로 분류한다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("broken", { status: 200 })),
    );
    await expect(apiRequest("/test")).rejects.toMatchObject({
      status: 200,
      code: "INVALID_RESPONSE",
    });
  });
  it("204를 정상 처리한다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );
    await expect(apiRequest("/test")).resolves.toBeUndefined();
  });
  it("외부 abort와 timeout을 구분한다", async () => {
    const abortingFetch = vi.fn(
      (_url, init: RequestInit) =>
        new Promise((_resolve, reject) =>
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          ),
        ),
    );
    vi.stubGlobal("fetch", abortingFetch);
    const external = new AbortController();
    const request = apiRequest("/test", { signal: external.signal }, 1000);
    external.abort();
    await expect(request).rejects.toMatchObject({ code: "REQUEST_ABORTED" });
    await expect(apiRequest("/test", {}, 1)).rejects.toMatchObject({
      code: "REQUEST_TIMEOUT",
    });
  });
  it("network 오류를 분류한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(apiRequest("/test")).rejects.toEqual(
      expect.objectContaining({ code: "NETWORK_ERROR" }),
    );
  });
  it("ApiError 인스턴스를 사용한다", () => {
    expect(normalizeApiError(500, null)).toBeInstanceOf(ApiError);
  });
});
