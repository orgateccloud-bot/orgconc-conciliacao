import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // O React Compiler NÃO está no build (sem babel-plugin-react-compiler no
      // vite.config). Estas regras vêm do preset v7 do eslint-plugin-react-hooks
      // e otimizam para um compilador ausente — acusam padrões de data-fetching
      // (setState em useEffect) e memoização manual que são válidos sem o compiler.
      // Mantemos rules-of-hooks e exhaustive-deps (clássicas). Reabilitar ao
      // adotar o React Compiler no build.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
      // Permite exportar constantes junto de componentes (padrão Vite/shadcn:
      // ex. buttonVariants em button.tsx). Hooks de Context usam disable pontual.
      'react-refresh/only-export-components': ['error', { allowConstantExport: true }],
    },
  },
])
