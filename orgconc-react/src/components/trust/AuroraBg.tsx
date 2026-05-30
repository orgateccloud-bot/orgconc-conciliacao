/**
 * AuroraBg — fundo decorativo do Trust Design System.
 *
 * Migrado de frontend/dashboard_trust.html (`.aurora-bg::before` / `::after`).
 * Renderiza dois blobs radiais animados (drift 24s/30s) em mix-blend.
 * Use uma vez por page (z-index 0, pointer-events none).
 */
export function AuroraBg() {
  return (
    <div
      className="fixed inset-0 z-0 pointer-events-none overflow-hidden"
      aria-hidden="true"
    >
      <div
        className="absolute rounded-full opacity-[0.35] dark:opacity-50 mix-blend-multiply dark:mix-blend-screen animate-aurora-drift-1"
        style={{
          width: 600,
          height: 600,
          top: -150,
          left: -100,
          filter: "blur(80px)",
          background: "radial-gradient(circle, #60A5FA 0%, transparent 70%)",
        }}
      />
      <div
        className="absolute rounded-full opacity-[0.35] dark:opacity-50 mix-blend-multiply dark:mix-blend-screen animate-aurora-drift-2"
        style={{
          width: 500,
          height: 500,
          bottom: -100,
          right: -50,
          filter: "blur(80px)",
          background: "radial-gradient(circle, #0EA5E9 0%, transparent 70%)",
        }}
      />
    </div>
  );
}
