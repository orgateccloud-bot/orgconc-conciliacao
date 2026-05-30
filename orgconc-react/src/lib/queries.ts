/**
 * Hooks TanStack Query — uso recomendado em vez de fetch direto.
 *
 * Exemplo:
 *   const { data, isLoading, error } = useClientes();
 *   const mut = useCriarCliente();
 *   mut.mutate({ nome: "X", ... });
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  atualizarCliente,
  carregarHistoricoLocal,
  criarCliente,
  listarClientes,
  listarConciliacoes,
  listarConciliacoesDoCliente,
  type Cliente,
  type ConciliacaoMeta,
} from "@/lib/api";

// ── Query Keys ─────────────────────────────────────────────────────────────

export const qk = {
  clientes: (apenasAtivos = true) => ["clientes", { apenasAtivos }] as const,
  cliente: (id: string) => ["clientes", id] as const,
  conciliacoes: (clienteId?: string) => ["conciliacoes", { clienteId }] as const,
  conciliacoesDoCliente: (clienteId: string) =>
    ["conciliacoes", "por-cliente", clienteId] as const,
  historicoLocal: () => ["historico-local"] as const,
} as const;

// ── Clientes ────────────────────────────────────────────────────────────────

export function useClientes(opts: { apenasAtivos?: boolean } = {}) {
  return useQuery({
    queryKey: qk.clientes(opts.apenasAtivos),
    queryFn: () => listarClientes(),
  });
}

export function useCriarCliente() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Cliente>) => criarCliente(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clientes"] }),
  });
}

export function useAtualizarCliente() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Cliente> }) =>
      atualizarCliente(id, data),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["clientes"] });
      qc.invalidateQueries({ queryKey: qk.cliente(vars.id) });
    },
  });
}

// ── Conciliacoes ────────────────────────────────────────────────────────────

export function useConciliacoes(clienteId?: string) {
  return useQuery({
    queryKey: qk.conciliacoes(clienteId),
    queryFn: () => listarConciliacoes(clienteId),
  });
}

export function useConciliacoesDoCliente(clienteId: string, enabled = true) {
  return useQuery({
    queryKey: qk.conciliacoesDoCliente(clienteId),
    queryFn: () => listarConciliacoesDoCliente(clienteId),
    enabled,
  });
}

export function useHistoricoLocal() {
  return useQuery({
    queryKey: qk.historicoLocal(),
    queryFn: () => carregarHistoricoLocal(),
    staleTime: 0,
  });
}

export type { Cliente, ConciliacaoMeta };
