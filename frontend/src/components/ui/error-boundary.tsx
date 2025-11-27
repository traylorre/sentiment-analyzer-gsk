'use client';

import { Component, type ReactNode, type ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorFallback
          error={this.state.error}
          onReset={this.handleReset}
          onReload={this.handleReload}
          onGoHome={this.handleGoHome}
        />
      );
    }

    return this.props.children;
  }
}

// Default error fallback component
interface ErrorFallbackProps {
  error: Error | null;
  onReset?: () => void;
  onReload?: () => void;
  onGoHome?: () => void;
}

export function ErrorFallback({
  error,
  onReset,
  onReload,
  onGoHome,
}: ErrorFallbackProps) {
  return (
    <div className="min-h-[400px] flex items-center justify-center p-4">
      <Card className="max-w-md w-full p-6 text-center">
        <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="w-8 h-8 text-red-500" />
        </div>

        <h2 className="text-xl font-semibold text-foreground mb-2">
          Something went wrong
        </h2>

        <p className="text-sm text-muted-foreground mb-4">
          We encountered an unexpected error. Please try again or refresh the page.
        </p>

        {error && process.env.NODE_ENV === 'development' && (
          <div className="mb-4 p-3 rounded-md bg-red-500/5 border border-red-500/20 text-left">
            <p className="text-xs font-mono text-red-500 break-all">
              {error.message}
            </p>
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-2">
          {onReset && (
            <Button variant="outline" onClick={onReset} className="flex-1 gap-2">
              <RefreshCw className="w-4 h-4" />
              Try Again
            </Button>
          )}
          {onReload && (
            <Button variant="outline" onClick={onReload} className="flex-1 gap-2">
              <RefreshCw className="w-4 h-4" />
              Reload Page
            </Button>
          )}
          {onGoHome && (
            <Button onClick={onGoHome} className="flex-1 gap-2">
              <Home className="w-4 h-4" />
              Go Home
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}

// Simple inline error display
interface InlineErrorProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function InlineError({
  title = 'Error',
  message,
  onRetry,
  className,
}: InlineErrorProps) {
  return (
    <div
      className={`flex items-center gap-3 p-4 rounded-lg bg-red-500/5 border border-red-500/20 ${className}`}
    >
      <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-red-500">{title}</p>
        <p className="text-xs text-red-500/80 truncate">{message}</p>
      </div>
      {onRetry && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onRetry}
          className="text-red-500 hover:text-red-600 hover:bg-red-500/10"
        >
          <RefreshCw className="w-4 h-4" />
        </Button>
      )}
    </div>
  );
}
