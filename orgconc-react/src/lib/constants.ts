// Mapas compartilhados de modo de conciliacao (badges e rotulos de pagina).
// Superset que cobre tanto os modos de resultado quanto os tiers de modelo.

export const MODO_CX: Record<string, string> = {
  simulacao_local: "bg-gray-100 text-gray-700 border-gray-200",
  simulacao:       "bg-gray-100 text-gray-700 border-gray-200",
  claude_llm:      "bg-blue-100 text-blue-700 border-blue-200",
  haiku:           "bg-sky-100 text-sky-700 border-sky-200",
  sonnet:          "bg-blue-100 text-blue-700 border-blue-200",
  fable:           "bg-purple-100 text-purple-700 border-purple-200",
  opus:            "bg-purple-100 text-purple-700 border-purple-200",
  multi_modelo:    "bg-purple-100 text-purple-700 border-purple-200",
  multi:           "bg-purple-100 text-purple-700 border-purple-200",
};

export const MODO_LABEL: Record<string, string> = {
  simulacao_local: "Simulação",
  simulacao:       "Simulação",
  claude_llm:      "Claude LLM",
  haiku:           "Haiku",
  sonnet:          "Sonnet",
  fable:           "Fable 5",
  opus:            "Opus",
  multi_modelo:    "Multi-modelo",
  multi:           "Multi-modelo",
};
