import * as Sentry from "@sentry/react";
import { APP_VERSION } from "@/lib/version";

const DSN = (import.meta.env.VITE_SENTRY_DSN as string | undefined)?.trim();
const ENV = (import.meta.env.MODE || "development").toLowerCase();

export function initSentry() {
  if (!DSN) return;
  Sentry.init({
    dsn: DSN,
    environment: ENV,
    release: APP_VERSION,
    sendDefaultPii: false,
    tracesSampleRate: 0.1,
    integrations: [
      Sentry.browserTracingIntegration(),
    ],
    beforeSend(event) {
      // Mascara emails em mensagens — backend ja faz para o servidor
      if (event.message) {
        event.message = event.message.replace(
          /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
          "***@***",
        );
      }
      return event;
    },
  });
}

export const SentryErrorBoundary = Sentry.ErrorBoundary;
