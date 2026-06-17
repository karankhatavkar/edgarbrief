import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { EmptyState } from "@/components/chat/EmptyState";
import { isApiError } from "@/lib/http";
import type { ChatOutletContext } from "@/components/chat/ChatLayout";

export default function ChatHome() {
  const { createThread, openSidebar } = useOutletContext<ChatOutletContext>();
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);

  async function start(text: string) {
    if (starting) return;
    setStarting(true);
    try {
      const thread = await createThread(text.slice(0, 60));
      // Hand the first message to the thread route, which auto-sends it.
      navigate(`/c/${thread.id}`, { state: { firstMessage: text } });
    } catch (err: unknown) {
      setStarting(false);
      console.error(isApiError(err) ? err.message : err);
    }
  }

  return <EmptyState onStart={start} starting={starting} onOpenSidebar={openSidebar} />;
}
