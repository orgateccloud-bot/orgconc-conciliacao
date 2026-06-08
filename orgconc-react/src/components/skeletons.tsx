import { Skeleton } from "@/components/ui/skeleton";

/**
 * Skeletons compartilhados pelas pages — substituem "Carregando..." generico.
 */

export function KpiCardSkeleton() {
  return (
    <div
      role="status"
      aria-label="Carregando indicador"
      className="relative overflow-hidden rounded-2xl border glass p-5"
    >
      <div className="flex items-start justify-between mb-3">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-6 w-6 rounded-lg" />
      </div>
      <Skeleton className="h-8 w-24 mb-2" />
      <Skeleton className="h-3 w-28" />
    </div>
  );
}

export function KpiGridSkeleton({ items = 4 }: { items?: number }) {
  return (
    <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: items }).map((_, i) => (
        <KpiCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function ListItemSkeleton() {
  return (
    <div className="flex items-center gap-4 rounded-xl px-4 py-3">
      <Skeleton className="h-2 w-2 rounded-full" />
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-3 w-32 flex-1" />
      <Skeleton className="h-3 w-16" />
      <Skeleton className="h-3 w-20" />
    </div>
  );
}

export function ListSkeleton({ items = 5 }: { items?: number }) {
  return (
    <div
      role="status"
      aria-label="Carregando lista"
      className="space-y-2"
    >
      {Array.from({ length: items }).map((_, i) => (
        <ListItemSkeleton key={i} />
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Carregando página"
      className="flex-1 flex flex-col gap-6 animate-fade-in"
    >
      <Skeleton className="h-36 rounded-3xl" />
      <KpiGridSkeleton />
      <div className="grid gap-5 lg:grid-cols-2">
        <Skeleton className="h-48 rounded-3xl" />
        <Skeleton className="h-48 rounded-3xl" />
      </div>
    </div>
  );
}

export function AppBootSkeleton() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Inicializando aplicação"
      className="min-h-screen flex items-center justify-center"
    >
      <div className="flex flex-col items-center gap-4">
        <Skeleton className="h-16 w-16 rounded-2xl" />
        <Skeleton className="h-3 w-40" />
      </div>
    </div>
  );
}
