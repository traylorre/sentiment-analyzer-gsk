import { Component, type ReactNode } from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorTrigger } from '@/components/ui/error-trigger';

class Boundary extends Component<{ children: ReactNode }, { message: string | null }> {
  state = { message: null as string | null };
  static getDerivedStateFromError(error: Error) {
    return { message: error.message };
  }
  render() {
    return this.state.message ? <p>caught: {this.state.message}</p> : this.props.children;
  }
}

describe('ErrorTrigger', () => {
  afterEach(() => {
    delete window.__TEST_FORCE_ERROR;
    vi.restoreAllMocks();
  });

  it('renders its children when the flag is unset', () => {
    render(
      <Boundary>
        <ErrorTrigger>
          <p>content</p>
        </ErrorTrigger>
      </Boundary>
    );

    expect(screen.getByText('content')).toBeInTheDocument();
  });

  it('throws into the nearest boundary when the flag is set', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    window.__TEST_FORCE_ERROR = true;

    render(
      <Boundary>
        <ErrorTrigger>
          <p>content</p>
        </ErrorTrigger>
      </Boundary>
    );

    expect(screen.getByText(/caught: TEST_FORCE_ERROR/)).toBeInTheDocument();
    expect(screen.queryByText('content')).not.toBeInTheDocument();
  });
});
