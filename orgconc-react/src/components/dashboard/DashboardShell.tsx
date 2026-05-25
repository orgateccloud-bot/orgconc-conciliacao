import type { ReactNode } from "react";

interface Props {
  main: ReactNode;
  rightbar?: ReactNode;
}

/**
 * Layout 3-colunas do dashboard. Sidebar global (esquerda) já vem do App.
 * Desktop ≥ xl (1280px): main flex + rightbar 280px lateral.
 * Mobile / tablet: empilha — rightbar abaixo do main.
 */
export function DashboardShell({ main, rightbar }: Props) {
  return (
    <div className="grid gap-6 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-6">{main}</div>
      {rightbar && (
        <aside className="xl:sticky xl:top-20 xl:self-start space-y-6">
          {rightbar}
        </aside>
      )}
    </div>
  );
}
