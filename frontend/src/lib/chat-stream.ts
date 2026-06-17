import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";
import type { ApiError } from "@/lib/http";

export interface StreamMessage {
  role: "user" | "assistant";
  content: string;
}

export interface StreamChatOptions {
  threadId: string;
  messages: StreamMessage[];
  onToken: (token: string) => void;
  signal?: AbortSignal;
}

/**
 * Stream one assistant turn from `POST /chat/stream`.
 *
 * The backend speaks the Vercel AI SDK data-stream protocol v1: newline-
 * delimited frames of the form `PREFIX:JSON`. We only act on two of them:
 *
 *   0:"token"             — a text delta (a JSON-encoded string)
 *   d:{"finishReason"…}   — the terminal finish frame
 *   3:"message"           — the protocol's error frame
 *
 * Any other frame type carries no text we render and is ignored.
 *
 * This is the one place we bypass the JSON `api` client: the response body is a
 * stream rather than a JSON document, so it needs a raw `fetch` + a
 * `ReadableStream` reader. The Supabase bearer is attached exactly the way the
 * `api` client attaches it.
 */
export async function streamChat({
  threadId,
  messages,
  onToken,
  signal,
}: StreamChatOptions): Promise<void> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  let response: Response;
  try {
    response = await fetch(`${env.API_BASE_URL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ thread_id: threadId, messages }),
      signal,
    });
  } catch (err) {
    // An aborted fetch must surface as an abort, not a network error.
    if (signal?.aborted) throw err;
    throw networkError();
  }

  if (!response.ok || !response.body) {
    throw await httpError(response);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newline: number;
    while ((newline = buffer.indexOf("\n")) !== -1) {
      const line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      handleFrame(line, onToken);
    }
  }

  // A final frame may arrive without a trailing newline.
  if (buffer.length > 0) handleFrame(buffer, onToken);
}

function handleFrame(line: string, onToken: (token: string) => void): void {
  const separator = line.indexOf(":");
  if (separator === -1) return;

  const prefix = line.slice(0, separator);
  const payload = line.slice(separator + 1);

  switch (prefix) {
    case "0":
      onToken(JSON.parse(payload) as string);
      return;
    case "3": {
      const err: ApiError = {
        status: 500,
        message: JSON.parse(payload) as string,
        isNetworkError: false,
      };
      throw err;
    }
  }
}

function networkError(): ApiError {
  return { status: 0, message: "Network error", isNetworkError: true };
}

async function httpError(response: Response): Promise<ApiError> {
  let message = response.statusText;
  try {
    const json = await response.json();
    message = json?.detail ?? json?.message ?? message;
  } catch {
    // leave message as statusText
  }
  return { status: response.status, message, isNetworkError: false };
}
