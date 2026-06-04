import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  retries: number;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, retries: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-8 text-center">
            <p className="text-2xl font-bold text-foreground">Algo deu errado</p>
            <p className="text-sm text-muted-foreground max-w-sm">
              {this.state.error?.message ?? "Erro inesperado. Recarregue a página."}
            </p>
            {this.state.retries >= 3 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                Número máximo de tentativas atingido. Recarregue a página.
              </p>
            ) : (
              <button
                className="mt-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                onClick={() =>
                  this.setState((s) => ({ hasError: false, error: undefined, retries: s.retries + 1 }))
                }
              >
                Tentar novamente
              </button>
            )}
          </div>
        )
      );
    }
    return this.props.children;
  }
}
