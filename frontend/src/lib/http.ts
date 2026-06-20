export interface ApiError {
  status: number;
  message: string;
  isNetworkError: boolean;
  /** Machine-readable reason from the backend (e.g. quota codes on a 429). */
  code?: string;
}

export function isApiError(err: unknown): err is ApiError {
  return typeof err === "object" && err !== null && "isNetworkError" in err;
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export async function request<T>(
  url: string,
  method: Method,
  body?: unknown,
  headers?: Record<string, string>,
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    const err: ApiError = { status: 0, message: "Network error", isNetworkError: true };
    throw err;
  }

  if (!response.ok) {
    throw await toApiError(response);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/**
 * Build an {@link ApiError} from a non-OK response.
 *
 * Reads FastAPI's `detail`, which is either a string or — for richer errors like
 * quota 429s — an object `{ code, message }`. The `code` lets callers branch on
 * the reason (e.g. user vs. global quota) without string-matching the message.
 */
export async function toApiError(response: Response): Promise<ApiError> {
  let message = response.statusText;
  let code: string | undefined;
  try {
    const json = await response.json();
    const detail = json?.detail;
    if (detail && typeof detail === "object") {
      message = detail.message ?? message;
      code = detail.code;
    } else {
      message = detail ?? json?.message ?? message;
    }
  } catch {
    // non-JSON body — keep statusText
  }
  return { status: response.status, message, isNetworkError: false, code };
}
