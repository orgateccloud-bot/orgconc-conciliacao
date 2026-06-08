import { ShieldCheck, Clock, Info } from "lucide-react";

// Badges honestos: certificação real ≠ "em andamento" ≠ nota de escopo.
// Cada categoria tem cor/ícone próprios — nada de pintar "não aplicável" de
// verde de conquista.
const CERTIFICADO = [
  { sigla: "LGPD", desc: "Conformidade com a Lei Geral de Proteção de Dados (Lei 13.709/18)" },
];
const EM_ANDAMENTO = [
  { sigla: "SOC 2", nota: "controles em andamento", desc: "Controles de segurança em implementação — certificação SOC 2 ainda não emitida" },
];
const ESCOPO = [
  { sigla: "PCI-DSS", nota: "não aplicável", desc: "A plataforma não armazena nem processa dados de cartão de pagamento" },
  { sigla: "BACEN", nota: "não é IF", desc: "Não é Instituição Financeira autorizada pelo BCB — ferramenta de análise documental" },
];

const BASE = "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-mono font-semibold uppercase tracking-wider";

export function ComplianceBadges() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {CERTIFICADO.map((b) => (
        <span
          key={b.sigla}
          title={b.desc}
          aria-label={`${b.sigla} — ${b.desc}`}
          className={`${BASE} border-green-200 dark:border-green-900/60 bg-green-50/80 dark:bg-green-950/30 text-green-700 dark:text-green-400`}
        >
          <ShieldCheck className="h-3 w-3" aria-hidden="true" />
          {b.sigla}
        </span>
      ))}
      {EM_ANDAMENTO.map((b) => (
        <span
          key={b.sigla}
          title={b.desc}
          aria-label={`${b.sigla} — ${b.desc}`}
          className={`${BASE} border-amber-200 dark:border-amber-900/60 bg-amber-50/80 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400`}
        >
          <Clock className="h-3 w-3" aria-hidden="true" />
          {b.sigla} <span className="font-normal normal-case opacity-70">· {b.nota}</span>
        </span>
      ))}
      {ESCOPO.map((b) => (
        <span
          key={b.sigla}
          title={b.desc}
          aria-label={`${b.sigla} — ${b.desc}`}
          className={`${BASE} border-border bg-muted/50 text-muted-foreground`}
        >
          <Info className="h-3 w-3" aria-hidden="true" />
          {b.sigla} <span className="font-normal normal-case opacity-70">· {b.nota}</span>
        </span>
      ))}
    </div>
  );
}
