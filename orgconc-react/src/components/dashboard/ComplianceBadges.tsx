import { ShieldCheck } from "lucide-react";

interface Badge {
  sigla: string;
  descricao: string;
}

const BADGES: Badge[] = [
  { sigla: "LGPD",                        descricao: "Conformidade com a Lei Geral de Proteção de Dados (Lei 13.709/18)" },
  { sigla: "SOC 2 (controles em andamento)", descricao: "Controles de segurança em implementação — certificação SOC 2 ainda não emitida" },
  { sigla: "PCI-DSS (não processa cartões)", descricao: "Padrão PCI-DSS não aplicável — a plataforma não armazena nem processa dados de cartão de pagamento" },
  { sigla: "BACEN (não é IF autorizada)",    descricao: "Não é Instituição Financeira autorizada pelo Banco Central do Brasil — ferramenta de análise documental" },
];

export function ComplianceBadges() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {BADGES.map((b) => (
        <span
          key={b.sigla}
          title={b.descricao}
          className="inline-flex items-center gap-1.5 rounded-full border border-green-200 dark:border-green-900/60 bg-green-50/80 dark:bg-green-950/30 px-2.5 py-1 text-[11px] font-mono font-semibold uppercase tracking-wider text-green-700 dark:text-green-400"
        >
          <ShieldCheck className="h-3 w-3" />
          {b.sigla}
        </span>
      ))}
    </div>
  );
}
