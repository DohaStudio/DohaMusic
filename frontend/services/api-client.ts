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

const userMessages: Record<string, string> = {
  NETWORK_ERROR: "음악 생성 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
  REQUEST_TIMEOUT: "응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.",
  VOICE_CONSENT_REQUIRED: "목소리 사용 동의를 확인해 주세요.",
  VOICE_FILE_TOO_LARGE: "파일 크기가 너무 큽니다. 25MB 이하 파일을 선택해 주세요.",
  VOICE_FILE_TYPE_UNSUPPORTED: "현재 WAV 파일만 지원합니다.",
  VOICE_PROFILE_IN_USE: "이 목소리는 생성 중인 음악에서 사용 중이라 삭제할 수 없습니다.",
  VOICE_ENROLLMENT_EXPIRED: "음성 등록 시간이 만료되었습니다. 새 등록을 시작해 주세요.",
  VOICE_NORMALIZER_UNAVAILABLE: "현재 서버에서는 이 녹음 형식을 처리할 수 없습니다. WAV 파일을 업로드해 주세요.",
  HTTP_ERROR: "요청을 처리하지 못했습니다. 입력 내용을 확인해 주세요.",
  PIPELINE_CANCEL_NOT_ALLOWED: "이미 완료되었거나 실패한 음악은 취소할 수 없습니다.",
  PIPELINE_RETRY_NOT_ALLOWED: "실패하거나 취소된 음악만 다시 만들 수 있습니다.",
  RETRY_VOICE_PROFILE_UNAVAILABLE: "사용한 목소리를 더 이상 사용할 수 없어 다시 만들 수 없습니다.",
  INVALID_KPOP_PRESET: "지원하지 않는 K-POP 스타일입니다.",
  INVALID_REQUESTED_BPM: "목표 BPM은 70에서 180 사이의 정수로 입력해 주세요.",
  INVALID_LANGUAGE_RATIO: "한국어와 영어 비율의 합은 100이어야 합니다.",
  INVALID_HOOK_OPTIONS: "후렴 Hook 설정을 확인해 주세요.",
  INVALID_VOCAL_ENERGY: "보컬 에너지 설정을 확인해 주세요.",
  INVALID_CONCEPT: "곡 콘셉트는 40자 이내로 입력해 주세요.",
  PRESET_GENRE_MISMATCH: "K-POP 스타일과 장르가 일치하지 않습니다.",
  PROJECT_NOT_FOUND: "Project를 찾을 수 없거나 접근 권한이 없습니다.",
  COMPOSITION_SNAPSHOT_NOT_FOUND: "선택한 Snapshot을 찾을 수 없습니다. 목록을 새로 확인해 주세요.",
  COMPOSITION_SNAPSHOT_CONFLICT: "Composition 상태가 변경되었습니다. 새로고침 후 다시 시도해 주세요.",
  WORKSPACE_BOOTSTRAP_REQUIRED: "작업 공간 준비가 필요합니다. 관리자에게 문의해 주세요.",
};

export function userErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
  return userMessages[error.code] ?? error.message;
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
    const headers = new Headers(init.headers);
    if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal,
      headers,
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
      const error = value as {
        code?: unknown;
        error_code?: unknown;
        message?: unknown;
      };
      return new ApiError(
        status,
        typeof error.code === "string"
          ? error.code
          : typeof error.error_code === "string"
            ? error.error_code
            : "HTTP_ERROR",
        typeof error.message === "string" ? error.message : fallback,
      );
    }
  }
  return new ApiError(status, "HTTP_ERROR", fallback);
}
