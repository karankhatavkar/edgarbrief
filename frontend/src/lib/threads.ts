import { api } from "@/lib/api";

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
