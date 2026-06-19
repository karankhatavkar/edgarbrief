import { LegalDocument01Icon } from "@hugeicons/core-free-icons";
import { Icon } from "@/components/icon";
import { CitationChips } from "@/components/chat/CitationChips";
import { Markdown } from "@/components/chat/Markdown";
import type { UiMessage } from "@/hooks/use-chat";
import type { SourcePassage } from "@/lib/citations";

interface MessageItemProps {
  message: UiMessage;
  onSelectPassage: (passage: SourcePassage) => void;
}

export function MessageItem({ message, onSelectPassage }: MessageItemProps) {
  if (message.role === "user") {
    return (
      <div className="animate-message-in flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-muted px-4 py-2.5 text-[15px] leading-relaxed text-foreground">
          {message.content}
        </div>
      </div>
    );
  }

  const thinking = message.streaming && message.content.length === 0;

  return (
    <div className="animate-message-in flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <div className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Icon icon={LegalDocument01Icon} size={13} />
        </div>
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
          EdgarBrief
        </span>
      </div>

      <div className="pl-8">
        {thinking ? (
          <div className="flex items-center gap-2.5 text-muted-foreground">
            <span className="flex gap-1">
              <span className="thinking-dot size-1.5 rounded-full bg-muted-foreground" style={{ animationDelay: "0ms" }} />
              <span className="thinking-dot size-1.5 rounded-full bg-muted-foreground" style={{ animationDelay: "160ms" }} />
              <span className="thinking-dot size-1.5 rounded-full bg-muted-foreground" style={{ animationDelay: "320ms" }} />
            </span>
            <span className="font-serif text-sm italic">Reviewing the filing…</span>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <Markdown>{message.content}</Markdown>
            {message.streaming && <span className="stream-caret" aria-hidden />}
            <CitationChips passages={message.citations ?? []} onSelect={onSelectPassage} />
          </div>
        )}
      </div>
    </div>
  );
}
