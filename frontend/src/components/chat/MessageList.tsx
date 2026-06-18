import { useEffect, useRef, useState } from "react";
import { MessageItem } from "@/components/chat/MessageItem";
import { MessageSkeleton } from "@/components/chat/MessageSkeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { UiMessage, ChatStatus } from "@/hooks/use-chat";
import type { SourcePassage } from "@/lib/citations";

interface MessageListProps {
  messages: UiMessage[];
  status: ChatStatus;
  error: string | null;
  retryable: boolean;
  onRetry: () => void;
  onSelectPassage: (passage: SourcePassage) => void;
}

export function MessageList({
  messages,
  status,
  error,
  retryable,
  onRetry,
  onSelectPassage,
}: MessageListProps) {
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
        {status === "loading" && <MessageSkeleton />}

        {empty && (
          <p className="py-10 text-center font-serif text-lg text-muted-foreground">
            Ask anything about the filing to begin.
          </p>
        )}

        {messages.map((message) => (
          <MessageItem key={message.id} message={message} onSelectPassage={onSelectPassage} />
        ))}

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Couldn’t complete that</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
            {retryable && (
              <div className="mt-2">
                <Button variant="outline" size="sm" onClick={onRetry}>
                  Try again
                </Button>
              </div>
            )}
          </Alert>
        )}

        <div ref={endRef} />
      </div>
    </div>
  );
}
