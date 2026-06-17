import { useEffect, useRef, useState } from "react";
import { MessageItem } from "@/components/chat/MessageItem";
import type { UiMessage, ChatStatus } from "@/hooks/use-chat";

interface MessageListProps {
  messages: UiMessage[];
  status: ChatStatus;
  error: string | null;
}

export function MessageList({ messages, status, error }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  // Follow the stream, but release if the reader scrolls up to re-read.
  const [stick, setStick] = useState(true);

  useEffect(() => {
    if (stick) endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, stick]);

  function onScroll() {
    const el = containerRef.current;
    if (!el) return;
    setStick(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  }

  const empty = messages.length === 0 && status !== "loading";

  return (
    <div ref={containerRef} onScroll={onScroll} className="ledger-canvas min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-7 px-4 py-8">
        {status === "loading" && (
          <p className="text-center font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Loading…
          </p>
        )}

        {empty && (
          <p className="py-10 text-center font-serif text-lg text-muted-foreground">
            Ask anything about the filing to begin.
          </p>
        )}

        {messages.map((message) => (
          <MessageItem key={message.id} message={message} />
        ))}

        {error && (
          <p
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            {error}
          </p>
        )}

        <div ref={endRef} />
      </div>
    </div>
  );
}
