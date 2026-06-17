export interface ApiError {
  status: number;
  message: string;
  isNetworkError: boolean;
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
    let message = response.statusText;
    try {
      const json = await response.json();
      message = json?.detail ?? json?.message ?? message;
    } catch {
      // leave message as statusText
    }
    const err: ApiError = { status: response.status, message, isNetworkError: false };
    throw err;
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
