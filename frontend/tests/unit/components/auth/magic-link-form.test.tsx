import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MagicLinkForm } from '@/components/auth/magic-link-form';

// Mock useAuth hook
const mockRequestMagicLink = vi.fn();
vi.mock('@/hooks/use-auth', () => ({
  useAuth: () => ({
    requestMagicLink: mockRequestMagicLink,
    isLoading: false,
  }),
}));

// Mock framer-motion - make sure motion components pass through properly
vi.mock('framer-motion', () => {
  const MotionDiv = ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
    // Filter out framer-motion specific props
    const htmlProps: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(props)) {
      if (!['initial', 'animate', 'exit', 'transition', 'variants', 'whileHover', 'whileTap'].includes(key)) {
        htmlProps[key] = value;
      }
    }
    return <div {...htmlProps}>{children}</div>;
  };

  return {
    motion: {
      div: MotionDiv,
    },
    AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
  };
});

describe('MagicLinkForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render email input and submit button', () => {
    render(<MagicLinkForm />);

    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /continue with email/i })
    ).toBeInTheDocument();
  });

  it('should disable button when email is empty', () => {
    render(<MagicLinkForm />);

    const button = screen.getByRole('button', { name: /continue with email/i });
    expect(button).toBeDisabled();
  });

  it('should enable button when email is entered', async () => {
    const user = userEvent.setup();
    render(<MagicLinkForm />);

    const input = screen.getByLabelText(/email address/i);
    await user.type(input, 'test@example.com');

    const button = screen.getByRole('button', { name: /continue with email/i });
    expect(button).not.toBeDisabled();
  });

  it('should not call API for invalid email', async () => {
    const user = userEvent.setup();
    render(<MagicLinkForm />);

    const input = screen.getByLabelText(/email address/i);
    // Use an email without @ to fail the regex
    await user.type(input, 'invalidemail');

    const button = screen.getByRole('button', { name: /continue with email/i });
    await user.click(button);

    // The API should not be called for invalid email
    expect(mockRequestMagicLink).not.toHaveBeenCalled();
  });

  it('should call requestMagicLink on valid submission', async () => {
    const user = userEvent.setup();
    mockRequestMagicLink.mockResolvedValueOnce(undefined);

    render(<MagicLinkForm />);

    const input = screen.getByLabelText(/email address/i);
    await user.type(input, 'test@example.com');

    const button = screen.getByRole('button', { name: /continue with email/i });
    await user.click(button);

    await waitFor(() => {
      expect(mockRequestMagicLink).toHaveBeenCalledWith(
        'test@example.com',
        'demo-captcha-token'
      );
    });
  });

  it('should show success state after sending', async () => {
    const user = userEvent.setup();
    mockRequestMagicLink.mockResolvedValueOnce(undefined);

    render(<MagicLinkForm />);

    const input = screen.getByLabelText(/email address/i);
    await user.type(input, 'test@example.com');

    const button = screen.getByRole('button', { name: /continue with email/i });
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
      expect(screen.getByText(/test@example.com/i)).toBeInTheDocument();
    });
  });

  it('should show error on API failure', async () => {
    const user = userEvent.setup();
    mockRequestMagicLink.mockRejectedValueOnce(new Error('Rate limited'));

    render(<MagicLinkForm />);

    const input = screen.getByLabelText(/email address/i);
    await user.type(input, 'test@example.com');

    const button = screen.getByRole('button', { name: /continue with email/i });
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/rate limited/i)).toBeInTheDocument();
    });
  });

  it('should call onSuccess callback after successful submission', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    mockRequestMagicLink.mockResolvedValueOnce(undefined);

    render(<MagicLinkForm onSuccess={onSuccess} />);

    const input = screen.getByLabelText(/email address/i);
    await user.type(input, 'test@example.com');

    const button = screen.getByRole('button', { name: /continue with email/i });
    await user.click(button);

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it('should allow using different email after success', async () => {
    const user = userEvent.setup();
    mockRequestMagicLink.mockResolvedValueOnce(undefined);

    render(<MagicLinkForm />);

    const input = screen.getByLabelText(/email address/i);
    await user.type(input, 'test@example.com');

    const submitButton = screen.getByRole('button', {
      name: /continue with email/i,
    });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    });

    const differentEmailButton = screen.getByRole('button', {
      name: /use a different email/i,
    });
    await user.click(differentEmailButton);

    // Should be back to form state
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
  });
});
