import { Skeleton } from "@/components/ui/skeleton";

/** Placeholder shown while a thread's history loads. */
export function MessageSkeleton() {
  return (
    <div className="flex flex-col gap-7" aria-hidden>
      <div className="flex justify-end">
        <Skeleton className="h-10 w-2/3 rounded-2xl rounded-br-md" />
      </div>
      <div className="flex flex-col gap-2">
        <Skeleton className="size-6 rounded-md" />
        <div className="flex flex-col gap-2 pl-8">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      </div>
    </div>
  );
}
