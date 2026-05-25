/** Placeholder de loading do dashboard — preserva o layout para evitar CLS. */
export function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Hero placeholder */}
      <div className="h-48 rounded-3xl bg-muted/40" />

      {/* KPI grid */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-32 rounded-2xl bg-muted/40" />
        ))}
      </div>

      {/* Charts */}
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="h-64 rounded-3xl bg-muted/40" />
        <div className="h-64 rounded-3xl bg-muted/40" />
      </div>

      {/* Tabela */}
      <div className="h-72 rounded-3xl bg-muted/40" />
    </div>
  );
}
