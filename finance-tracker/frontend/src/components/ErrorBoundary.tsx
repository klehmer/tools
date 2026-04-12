import React from "react";

interface State {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; label?: string },
  State
> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log to the console so the root cause is recoverable from devtools.
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", this.props.label, error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div className="m-4 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <div className="mb-1 font-semibold">
            Something went wrong{this.props.label ? ` in ${this.props.label}` : ""}.
          </div>
          <div className="font-mono text-xs">{this.state.error.message}</div>
          <button
            onClick={this.reset}
            className="mt-3 rounded-md border border-rose-300 bg-white px-3 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
