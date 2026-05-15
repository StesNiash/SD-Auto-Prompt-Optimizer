import { Component, type ReactNode } from "react";

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, background: "#0f172a", color: "#ef4444", minHeight: "100vh" }}>
          <h2>Something went wrong</h2>
          <pre style={{ color: "#e2e8f0", fontSize: 13, whiteSpace: "pre-wrap" }}>
            {this.state.error.message}
            {"\n\n"}{this.state.error.stack}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}