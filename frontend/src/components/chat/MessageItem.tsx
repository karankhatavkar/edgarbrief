import { LegalDocument01Icon } from "@hugeicons/core-free-icons";
import { Icon } from "@/components/icon";
import type { UiMessage } from "@/hooks/use-chat";

export function MessageItem({ message }: { message: UiMessage }) {
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
          <p className="whitespace-pre-wrap break-words font-serif text-[16px] leading-[1.7] text-foreground">
            {message.content}
            {message.streaming && <span className="stream-caret align-baseline" aria-hidden />}
          </p>
        )}
      </div>
    </div>
  );
}
