const DEFAULT_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
    if (response.status === 204) return undefined as T;
    if (!response.ok) {
      let payload: unknown;
      try { payload = await response.json(); } catch { payload = null; }
      throw normalizeApiError(response.status, payload);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") throw new ApiError(0, "REQUEST_TIMEOUT", "서버 응답 시간이 초과되었습니다.");
    throw new ApiError(0, "NETWORK_ERROR", "Backend에 연결할 수 없습니다.");
  } finally { clearTimeout(timeout); }
}

export function normalizeApiError(status: number, body: unknown): ApiError {
  const fallback = status === 404 ? "요청한 리소스를 찾을 수 없습니다." : "요청을 처리하지 못했습니다.";
  if (body && typeof body === "object" && "error" in body) {
    const value = (body as { error?: unknown }).error;
    if (value && typeof value === "object") {
      const error = value as { code?: unknown; message?: unknown };
      return new ApiError(status, typeof error.code === "string" ? error.code : "HTTP_ERROR", typeof error.message === "string" ? error.message : fallback);
    }
  }
  return new ApiError(status, "HTTP_ERROR", fallback);
}
