import { useEffect, useRef } from "react";
import { useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";
import { Menu01Icon } from "@hugeicons/core-free-icons";
import { Icon } from "@/components/icon";
import { MessageList } from "@/components/chat/MessageList";
import { Composer } from "@/components/chat/Composer";
import { useChat } from "@/hooks/use-chat";
import type { ChatOutletContext } from "@/components/chat/ChatLayout";

export default function ChatThread() {
  const { threadId = "" } = useParams();
  // Key by threadId so switching threads remounts with fresh chat state.
  return <ChatThreadView key={threadId} threadId={threadId} />;
}

function ChatThreadView({ threadId }: { threadId: string }) {
  const { threads, openSidebar, refreshThreads } = useOutletContext<ChatOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();

  const { messages, status, error, send, stop } = useChat(threadId);
  const title = threads.find((t) => t.id === threadId)?.title ?? "New brief";

  // A first message handed over from the home screen, auto-sent exactly once.
  const consumed = useRef(false);
  const firstMessage = (location.state as { firstMessage?: string } | null)?.firstMessage;

  useEffect(() => {
    if (!firstMessage || consumed.current || status !== "idle") return;
    consumed.current = true;
    // Clear the router state so a reload doesn't replay the send.
    navigate(location.pathname, { replace: true, state: null });
    void send(firstMessage).then(refreshThreads);
  }, [firstMessage, status, send, navigate, location.pathname, refreshThreads]);

  async function handleSend(text: string) {
    await send(text);
    await refreshThreads();
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-2.5 border-b bg-background/80 px-4 py-3 backdrop-blur">
        <button
          onClick={openSidebar}
          aria-label="Open menu"
          className="rounded-md p-1.5 hover:bg-muted md:hidden"
        >
          <Icon icon={Menu01Icon} size={20} />
        </button>
        <h1 className="min-w-0 flex-1 truncate font-serif text-[17px] tracking-tight">{title}</h1>
        <span className="hidden font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground sm:inline">
          Phase 3 · stub
        </span>
      </header>

      <MessageList messages={messages} status={status} error={error} />
      <Composer onSend={handleSend} status={status} onStop={stop} />
    </div>
  );
}
