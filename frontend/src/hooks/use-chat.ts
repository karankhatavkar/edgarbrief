import { useCallback, useEffect, useRef, useState } from "react";
import { listMessages, type Message } from "@/lib/threads";
import { streamChat } from "@/lib/chat-stream";
import { isApiError } from "@/lib/http";
import { supabase } from "@/lib/supabase";
import type { SourcePassage } from "@/lib/citations";

export type ChatStatus = "loading" | "idle" | "streaming" | "error";

export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Cited source passages backing an assistant answer (empty when none). */
  citations?: SourcePassage[];
  /** True while this assistant message is still receiving tokens. */
  streaming?: boolean;
}

export interface UseChat {
  messages: UiMessage[];
  status: ChatStatus;
  error: string | null;
  send: (text: string) => Promise<void>;
  /** Re-run the last turn after a failure, without re-asking the question. */
  retry: () => void;
  retryable: boolean;
  stop: () => void;
}

/**
 * Drive one chat thread: load its history, then stream assistant turns.
 *
 * Mirrors the small slice of the AI SDK `useChat` surface we actually use, but
 * speaks directly to our backend through {@link streamChat}. State is kept in a
 * ref alongside React state so a turn can read the latest message list without
 * being torn down and recreated on every token.
 */
export function useChat(threadId: string): UseChat {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  // Whether the last failure was a turn we can re-run (vs. a load failure).
  const [retryable, setRetryable] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<UiMessage[]>(messages);

  // Keep a ref to the latest messages so a turn can build its payload without
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
        setMessages(
          rows.map((r) => ({
            id: r.id,
            role: r.role,
            content: r.content,
            citations: r.citations ?? [],
          })),
        );
        setStatus("idle");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setRetryable(false);
        setError(messageForError(err));
        setStatus("error");
        if (isApiError(err) && err.status === 401) void supabase.auth.signOut();
      });

    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [threadId]);

  // Stream one assistant turn for the given conversation. Appends the assistant
  // bubble and fills it with tokens and citations as they arrive.
  const runTurn = useCallback(
    async (outgoing: { role: "user" | "assistant"; content: string }[]) => {
      const assistantId = crypto.randomUUID();

      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "", citations: [], streaming: true },
      ]);
      setStatus("streaming");
      setError(null);

      const controller = new AbortController();
      abortRef.current = controller;

      const update = (patch: (m: UiMessage) => UiMessage) =>
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? patch(m) : m)));

      try {
        await streamChat({
          threadId,
          messages: outgoing,
          signal: controller.signal,
          onToken: (token) => update((m) => ({ ...m, content: m.content + token })),
          onCitations: (passages) => update((m) => ({ ...m, citations: passages })),
        });
        update((m) => ({ ...m, streaming: false }));
        setStatus("idle");
      } catch (err: unknown) {
        // A user-initiated stop keeps whatever streamed so far.
        if (controller.signal.aborted) {
          update((m) => ({ ...m, streaming: false }));
          setStatus("idle");
          return;
        }
        // Drop the empty assistant bubble; the user's question stays so `retry`
        // can re-run the turn against it.
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        setRetryable(true);
        setError(messageForError(err));
        setStatus("error");
        if (isApiError(err) && err.status === 401) void supabase.auth.signOut();
      } finally {
        abortRef.current = null;
      }
    },
    [threadId],
  );

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content || status === "streaming") return;

      const outgoing = [
        ...messagesRef.current.map((m) => ({ role: m.role, content: m.content })),
        { role: "user" as const, content },
      ];

      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", content },
      ]);
      await runTurn(outgoing);
    },
    [status, runTurn],
  );

  const retry = useCallback(() => {
    if (status === "streaming") return;
    const outgoing = messagesRef.current.map((m) => ({ role: m.role, content: m.content }));
    // Only meaningful when the last message is the question that failed.
    if (outgoing[outgoing.length - 1]?.role !== "user") return;
    void runTurn(outgoing);
  }, [status, runTurn]);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { messages, status, error, send, retry, retryable, stop };
}

function messageForError(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 401) return "Session expired — please sign in again.";
    if (err.status === 403) return "You don't have access to this conversation.";
    if (err.isNetworkError) return "Connection lost — check your network and try again.";
    return err.message || "Something went wrong — please try again.";
  }
  return "The assistant failed to respond.";
}
