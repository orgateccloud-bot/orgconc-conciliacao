/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Auto-login DEV: service token enviado como Bearer enquanto a tela de login é refeita.
   *  Opcional — vazio quando o backend dev aceita acesso anônimo. */
  readonly VITE_DEV_AUTH_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
