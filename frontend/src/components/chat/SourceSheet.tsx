import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons";
import { Icon } from "@/components/icon";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/chat/Markdown";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { filingLabel, locationLabel, type SourcePassage } from "@/lib/citations";

interface SourceSheetProps {
  passage: SourcePassage | null;
  onClose: () => void;
}

/**
 * The verification surface: the exact filing passage behind a citation, shown
 * as a record card — mono provenance header, the excerpt in the same serif the
 * answer is set in, and a link out to the filing on SEC.gov.
 */
export function SourceSheet({ passage, onClose }: SourceSheetProps) {
  return (
    <Sheet open={passage !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full gap-0 sm:max-w-lg">
        {passage && (
          <>
            <SheetHeader className="gap-2 border-b">
              <SheetTitle className="font-serif text-lg tracking-tight">
                {passage.company}
              </SheetTitle>
              <SheetDescription className="flex flex-col gap-0.5 font-mono text-[11px] tracking-wide">
                <span className="text-foreground">{filingLabel(passage)}</span>
                <span>
                  {[locationLabel(passage), formatFilingDate(passage.filing_date)]
                    .filter(Boolean)
                    .join(" · ") || "Filing excerpt"}
                </span>
              </SheetDescription>
            </SheetHeader>

            <ScrollArea className="min-h-0 flex-1">
              <div className="px-6 py-6">
                <Markdown className="text-[15px]">{passage.excerpt}</Markdown>
              </div>
            </ScrollArea>

            <SheetFooter className="border-t">
              <Button asChild variant="outline" className="w-full">
                <a href={passage.source_url} target="_blank" rel="noopener noreferrer">
                  View on SEC
                  <Icon icon={ArrowUpRight01Icon} size={15} />
                </a>
              </Button>
            </SheetFooter>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function formatFilingDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
