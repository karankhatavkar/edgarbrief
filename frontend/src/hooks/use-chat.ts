import { useCallback, useEffect, useRef, useState } from "react";
import { listMessages, type Message } from "@/lib/threads";
import { streamChat } from "@/lib/chat-stream";
import { isApiError } from "@/lib/http";

export type ChatStatus = "loading" | "idle" | "streaming" | "error";

export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** True while this assistant message is still receiving tokens. */
  streaming?: boolean;
}

export interface UseChat {
  messages: UiMessage[];
  status: ChatStatus;
  error: string | null;
  send: (text: string) => Promise<void>;
  stop: () => void;
}

/**
 * Drive one chat thread: load its history, then stream assistant turns.
 *
 * Mirrors the small slice of the AI SDK `useChat` surface we actually use, but
 * speaks directly to our backend through {@link streamChat}. State is kept in a
 * ref alongside React state so `send` can read the latest message list without
 * being torn down and recreated on every token.
 */
export function useChat(threadId: string): UseChat {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<UiMessage[]>(messages);

  // Keep a ref to the latest messages so `send` can build its payload without
  // being recreated on every streamed token. Synced in an effect rather than
  // during render.
  useEffect(() => {
    messagesRef.current = messages;
  });

  // Load persisted history for this thread. The consumer keys the component by
  // threadId, so a thread switch remounts with fresh "loading" state and this
  // runs again — no synchronous reset needed here.
  useEffect(() => {
    let cancelled = false;

    listMessages(threadId)
      .then((rows: Message[]) => {
        if (cancelled) return;
        setMessages(rows.map((r) => ({ id: r.id, role: r.role, content: r.content })));
        setStatus("idle");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(isApiError(err) ? err.message : "Failed to load this conversation.");
        setStatus("error");
      });

    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [threadId]);

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content || status === "streaming") return;

      const userMessage: UiMessage = { id: crypto.randomUUID(), role: "user", content };
      const assistantId = crypto.randomUUID();

      // Build the outgoing payload from the conversation *before* this turn.
      const outgoing = [
        ...messagesRef.current.map((m) => ({ role: m.role, content: m.content })),
        { role: "user" as const, content },
      ];

      setMessages((prev) => [
        ...prev,
        userMessage,
        { id: assistantId, role: "assistant", content: "", streaming: true },
      ]);
      setStatus("streaming");
      setError(null);

      const controller = new AbortController();
      abortRef.current = controller;

      const clearStreaming = () =>
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
        );

      try {
        await streamChat({
          threadId,
          messages: outgoing,
          signal: controller.signal,
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + token } : m,
              ),
            );
          },
        });
        clearStreaming();
        setStatus("idle");
      } catch (err: unknown) {
        // A user-initiated stop keeps whatever streamed so far.
        if (controller.signal.aborted) {
          clearStreaming();
          setStatus("idle");
          return;
        }
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        setError(isApiError(err) ? err.message : "The assistant failed to respond.");
        setStatus("error");
      } finally {
        abortRef.current = null;
      }
    },
    [threadId, status],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { messages, status, error, send, stop };
}
