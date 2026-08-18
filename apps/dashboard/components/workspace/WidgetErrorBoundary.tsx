"use client";

import { Component, type ReactNode } from "react";

interface Props {
  widgetTitle: string;
  critical?: boolean;
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

// Sprint 15 §4.11: a rendering failure in one widget must not destroy the
// rest of the CEO Workspace. This is the ONLY place a widget's render
// errors are caught -- no raw stack trace, no payload, ever shown to the
// CEO (Rule #7/#18: fail visibly, but never leak internals). `critical`
// marks the primary next-action slot, which gets a stronger, non-dismissable
// fallback per §4.11's explicit requirement rather than the generic card,
// since silently losing the CEO's main action is the one failure this
// system must never produce.
export class WidgetErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error(`CEO Workspace: widget "${this.props.widgetTitle}" failed to render.`, error);
  }

  private retry = () => this.setState({ hasError: false });

  render() {
    if (!this.state.hasError) return this.props.children;

    if (this.props.critical) {
      return (
        <section className="rounded-xl border border-status-amber/40 bg-status-amber-soft p-5 shadow-panel">
          <h2 className="text-base font-semibold text-text">Something needs a look</h2>
          <p className="mt-1 text-sm text-text-muted">
            Your main action couldn&apos;t be displayed. Refresh to try again.
          </p>
          <button
            type="button"
            onClick={this.retry}
            className="mt-4 inline-block rounded-lg border border-base-border bg-base-card px-4 py-2 text-sm font-medium text-text-muted hover:bg-base-hover"
          >
            Refresh
          </button>
        </section>
      );
    }

    return (
      <div className="rounded-xl border border-dashed border-status-red/40 bg-status-red-soft px-4 py-6 text-center">
        <p className="text-sm font-medium text-status-red">{this.props.widgetTitle} couldn&apos;t load.</p>
        <button
          type="button"
          onClick={this.retry}
          className="mt-2 rounded-lg border border-base-border bg-base-card px-3 py-1.5 text-xs font-medium text-text-muted hover:bg-base-hover"
        >
          Retry
        </button>
      </div>
    );
  }
}
