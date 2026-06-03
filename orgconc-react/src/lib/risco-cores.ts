export const CLASSE_COLOR_BADGE: Record<string, string> = {
  BAIXO:   'bg-green-100 text-green-800 border border-green-200',
  MEDIO:   'bg-yellow-100 text-yellow-800 border border-yellow-200',
  ALTO:    'bg-orange-100 text-orange-800 border border-orange-200',
  CRITICO: 'bg-red-100 text-red-800 border border-red-200',
}
export const CLASSE_COLOR_BAR: Record<string, string> = {
  BAIXO: 'bg-green-500', MEDIO: 'bg-yellow-500', ALTO: 'bg-orange-500', CRITICO: 'bg-red-500',
}
export function corBadge(classe: string): string {
  return CLASSE_COLOR_BADGE[classe] ?? 'bg-gray-100 text-gray-800 border border-gray-200'
}
