import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OAuthButton, OAuthButtons, AuthDivider } from '@/components/auth/oauth-buttons';

// Mock useAuth hook
const mockSignInOAuth = vi.fn();
vi.mock('@/hooks/use-auth', () => ({
  useAuth: () => ({
    signInOAuth: mockSignInOAuth,
  }),
}));

describe('OAuthButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Google button', () => {
    it('should render Google button with correct label', () => {
      render(<OAuthButton provider="google" />);

      expect(
        screen.getByRole('button', { name: /continue with google/i })
      ).toBeInTheDocument();
    });

    it('should call signInOAuth with google provider', async () => {
      const user = userEvent.setup();
      render(<OAuthButton provider="google" />);

      const button = screen.getByRole('button', { name: /continue with google/i });
      await user.click(button);

      await waitFor(() => {
        expect(mockSignInOAuth).toHaveBeenCalledWith('google');
      });
    });

    it('should be disabled when disabled prop is true', () => {
      render(<OAuthButton provider="google" disabled />);

      const button = screen.getByRole('button', { name: /continue with google/i });
      expect(button).toBeDisabled();
    });
  });

  describe('GitHub button', () => {
    it('should render GitHub button with correct label', () => {
      render(<OAuthButton provider="github" />);

      expect(
        screen.getByRole('button', { name: /continue with github/i })
      ).toBeInTheDocument();
    });

    it('should call signInOAuth with github provider', async () => {
      const user = userEvent.setup();
      render(<OAuthButton provider="github" />);

      const button = screen.getByRole('button', { name: /continue with github/i });
      await user.click(button);

      await waitFor(() => {
        expect(mockSignInOAuth).toHaveBeenCalledWith('github');
      });
    });
  });

  describe('loading state', () => {
    it('should show loading spinner when clicked', async () => {
      const user = userEvent.setup();
      // Make signInOAuth never resolve to keep loading state
      mockSignInOAuth.mockImplementation(() => new Promise(() => {}));

      render(<OAuthButton provider="google" />);

      const button = screen.getByRole('button', { name: /continue with google/i });
      await user.click(button);

      // Button should still be in the DOM but with loading state
      await waitFor(() => {
        expect(button).toBeDisabled();
      });
    });
  });
});

describe('OAuthButtons', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render both Google and GitHub buttons', () => {
    render(<OAuthButtons />);

    expect(
      screen.getByRole('button', { name: /continue with google/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /continue with github/i })
    ).toBeInTheDocument();
  });

  it('should disable all buttons when disabled prop is true', () => {
    render(<OAuthButtons disabled />);

    const googleButton = screen.getByRole('button', {
      name: /continue with google/i,
    });
    const githubButton = screen.getByRole('button', {
      name: /continue with github/i,
    });

    expect(googleButton).toBeDisabled();
    expect(githubButton).toBeDisabled();
  });

  it('should apply custom className', () => {
    const { container } = render(<OAuthButtons className="custom-class" />);

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('custom-class');
  });
});

describe('AuthDivider', () => {
  it('should render divider with "Or continue with" text', () => {
    render(<AuthDivider />);

    expect(screen.getByText(/or continue with/i)).toBeInTheDocument();
  });

  it('should apply custom className', () => {
    const { container } = render(<AuthDivider className="custom-divider" />);

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('custom-divider');
  });
});
