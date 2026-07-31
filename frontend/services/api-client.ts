const DEFAULT_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const timeoutController = new AbortController();
  const timeout = setTimeout(() => timeoutController.abort(), timeoutMs);
  const signal = init.signal
    ? AbortSignal.any([init.signal, timeoutController.signal])
    : timeoutController.signal;
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
    if (response.status === 204) return undefined as T;
    if (!response.ok) {
      const payload = await safeJson(response);
      throw normalizeApiError(response.status, payload);
    }
    try {
      return (await response.json()) as T;
    } catch {
      throw new ApiError(
        response.status,
        "INVALID_RESPONSE",
        "서버 응답 형식이 올바르지 않습니다.",
      );
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (isAbortError(error)) {
      if (init.signal?.aborted) {
        throw new ApiError(0, "REQUEST_ABORTED", "요청이 취소되었습니다.");
      }
      throw new ApiError(
        0,
        "REQUEST_TIMEOUT",
        "서버 응답 시간이 초과되었습니다.",
      );
    }
    throw new ApiError(0, "NETWORK_ERROR", "Backend에 연결할 수 없습니다.");
  } finally {
    clearTimeout(timeout);
  }
}

async function safeJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function normalizeApiError(status: number, body: unknown): ApiError {
  const fallback =
    status === 404
      ? "요청한 리소스를 찾을 수 없습니다."
      : "요청을 처리하지 못했습니다.";
  if (body && typeof body === "object" && "error" in body) {
    const value = (body as { error?: unknown }).error;
    if (value && typeof value === "object") {
      const error = value as { code?: unknown; message?: unknown };
      return new ApiError(
        status,
        typeof error.code === "string" ? error.code : "HTTP_ERROR",
        typeof error.message === "string" ? error.message : fallback,
      );
    }
  }
  return new ApiError(status, "HTTP_ERROR", fallback);
}
