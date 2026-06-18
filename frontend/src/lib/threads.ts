import { api } from "@/lib/api";
import type { SourcePassage } from "@/lib/citations";

/** A chat thread as returned by the backend (`/threads`). */
export interface Thread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

/** A persisted message as returned by `/threads/{id}/messages`. */
export interface Message {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  /** Cited source passages — present on assistant messages that cited sources. */
  citations?: SourcePassage[];
}

export function listThreads(): Promise<Thread[]> {
  return api.get<Thread[]>("/threads");
}

export function createThread(title?: string): Promise<Thread> {
  return api.post<Thread>("/threads", title ? { title } : {});
}

export function listMessages(threadId: string): Promise<Message[]> {
  return api.get<Message[]>(`/threads/${threadId}/messages`);
}
