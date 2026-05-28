import { useEffect, useState } from "react";
import {
  fiscalConformidade,
  listarClientes,
  type Cliente,
  type FiscalConformidadeResponse,
} from "@/lib/api";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { HeroCard } from "@/components/HeroCard";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Filter, FileWarning } from "lucide-react";

const CLASSE_COLOR: Record<string, string> = {
  BAIXO: "bg-green-100 text-green-700 border-green-200",
  MEDIO: "bg-blue-100 text-blue-700 border-blue-200",
  ALTO: "bg-orange-100 text-orange-700 border-orange-200",
  CRITICO: "bg-red-100 text-red-700 border-red-200",
};

function formatBRL(v: number): string {
  return v.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  });
}

export function GapsFiscaisPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clienteId, setClienteId] = useState<string>("");
  const [classe, setClasse] = useState<string>("");
  const [dados, setDados] = useState<FiscalConformidadeResponse | null>(null);
  const [search, setSearch] = useState<string>("");

  useEffect(() => {
    listarClientes()
      .then(setClientes)
      .catch(() => toast.error("Falha ao carregar clientes"));
  }, []);

  useEffect(() => {
    if (!clienteId) {
      setDados(null);
      return;
    }
    fiscalConformidade(clienteId, classe || undefined)
      .then(setDados)
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "Falha ao carregar gaps"),
      );
  }, [clienteId, classe]);

  const fornecedoresFiltrados = (dados?.fornecedores ?? []).filter((f) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      f.cnpj.toLowerCase().includes(s) ||
      (f.razao_social ?? "").toLowerCase().includes(s)
    );
  });

  return (
    <div className="space-y-8">
      <HeroCard
        eyebrow="FISCAL · GAPS"
        title="Gaps fiscais"
        titleAccent="por fornecedor."
        subtitle="Lista paginada de fornecedores com lacunas entre pagamentos e documentos fiscais. Use os filtros para focar no risco prioritário."
      />

      <section className="rounded-3xl border glass p-6 space-y-5">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label>Cliente</Label>
            <Select value={clienteId} onValueChange={setClienteId}>
              <SelectTrigger>
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent>
                {clientes.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.nome}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Classe mínima de risco</Label>
            <Select value={classe || "TODOS"} onValueChange={(v) => setClasse(v === "TODOS" ? "" : v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="TODOS">Todos</SelectItem>
                <SelectItem value="MEDIO">Médio ou superior</SelectItem>
                <SelectItem value="ALTO">Alto ou superior</SelectItem>
                <SelectItem value="CRITICO">Apenas crítico</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Buscar (CNPJ/razão)</Label>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filtrar..."
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </div>
        </div>

        {dados && (
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <Filter className="h-4 w-4" />
            <span>
              <strong className="text-foreground">{fornecedoresFiltrados.length}</strong> fornecedor(es) exibidos · total{" "}
              <strong className="text-foreground">{dados.total}</strong>
            </span>
          </div>
        )}

        {dados && fornecedoresFiltrados.length === 0 && (
          <div className="rounded-xl border-dashed border-2 p-10 text-center text-muted-foreground">
            <FileWarning className="h-10 w-10 mx-auto mb-2 opacity-50" />
            Nenhum fornecedor para os filtros atuais.
          </div>
        )}

        {fornecedoresFiltrados.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="py-2 px-2">#</th>
                  <th className="py-2 px-2">Fornecedor</th>
                  <th className="py-2 px-2">CNPJ</th>
                  <th className="py-2 px-2 text-right">Pagamentos</th>
                  <th className="py-2 px-2 text-right">Volume Pago</th>
                  <th className="py-2 px-2 text-right">NFs</th>
                  <th className="py-2 px-2 text-right">Volume NF</th>
                  <th className="py-2 px-2 text-right">Conformidade</th>
                  <th className="py-2 px-2 text-right">Risco Anual</th>
                  <th className="py-2 px-2">Classe</th>
                  <th className="py-2 px-2">Flags</th>
                </tr>
              </thead>
              <tbody>
                {fornecedoresFiltrados.map((f, i) => (
                  <tr key={f.cnpj} className="border-b hover:bg-muted/30">
                    <td className="py-2 px-2">{i + 1}</td>
                    <td className="py-2 px-2 font-medium">{f.razao_social || "—"}</td>
                    <td className="py-2 px-2 font-mono text-xs">{f.cnpj}</td>
                    <td className="py-2 px-2 text-right">{f.n_pagamentos}</td>
                    <td className="py-2 px-2 text-right">{formatBRL(f.volume_pago)}</td>
                    <td className="py-2 px-2 text-right">{f.n_nfes}</td>
                    <td className="py-2 px-2 text-right">{formatBRL(f.volume_nf)}</td>
                    <td className="py-2 px-2 text-right">{f.conformidade_pct.toFixed(1)}%</td>
                    <td className="py-2 px-2 text-right font-semibold text-red-600">
                      {formatBRL(f.risco_tributario_anual)}
                    </td>
                    <td className="py-2 px-2">
                      <span className={cn(
                        "inline-block px-2 py-0.5 rounded text-xs font-semibold border",
                        CLASSE_COLOR[f.risco_classe] ?? "",
                      )}>
                        {f.risco_classe}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-xs text-muted-foreground">
                      {f.flags.join(", ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
