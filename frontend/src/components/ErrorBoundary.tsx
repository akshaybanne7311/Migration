import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // eslint-disable-next-line no-console
    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "var(--bg)" }}>
        <div className="neon-card bg-white border border-red-200 rounded-lg shadow-sm p-6 max-w-md w-full text-center">
          <div className="font-display text-lg font-semibold text-slate-900 mb-2">
            Something went wrong
          </div>
          <p className="text-sm text-slate-500 mb-1">
            The UI hit an unexpected error and couldn't continue rendering this view.
          </p>
          <p className="text-xs text-slate-400 mb-4 font-mono break-all">{this.state.error.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="neon-btn text-sm font-medium rounded-md px-4 py-2 bg-blue-600 text-white"
          >
            Reload the app
          </button>
        </div>
      </div>
    );
  }
}
