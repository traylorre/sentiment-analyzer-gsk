'use client';

/**
 * OAuth Callback Page - Handles OAuth provider redirects.
 *
 * Feature 1192: Receives authorization code from OAuth providers (Google/GitHub),
 * exchanges it for tokens via handleCallback(), and redirects to dashboard.
 *
 * Flow:
 * 1. OAuth provider redirects here with ?code=XXX&state=YYY
 * 2. Page retrieves stored provider from sessionStorage (set by signInWithOAuth)
 * 3. Calls handleCallback(code, provider) to exchange code for tokens
 * 4. On success, redirects to dashboard after brief success message
 * 5. On error, displays message with retry option
 */

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Check, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/use-auth';
import type { OAuthProvider } from '@/types/auth';

function CallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { handleCallback, isLoading, error: authError } = useAuth();

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasProcessed, setHasProcessed] = useState(false);

  const code = searchParams.get('code');
  const errorParam = searchParams.get('error');
  const errorDescription = searchParams.get('error_description');

  useEffect(() => {
    // Prevent double-processing (React StrictMode or re-renders)
    if (hasProcessed) return;
    setHasProcessed(true);

    // Handle OAuth provider denial (user clicked "Deny" or error occurred)
    if (errorParam) {
      setStatus('error');
      setErrorMessage(
        errorDescription
          ? `Authentication failed: ${errorDescription}`
          : 'Authentication was cancelled'
      );
      return;
    }

    // Retrieve and clear stored provider (set by signInWithOAuth before redirect)
    // Feature 1192: sessionStorage ensures cross-tab isolation
    const provider = sessionStorage.getItem('oauth_provider') as OAuthProvider | null;
    sessionStorage.removeItem('oauth_provider');

    // Validate required parameters
    if (!code) {
      setStatus('error');
      setErrorMessage('Invalid callback: missing authorization code');
      return;
    }

    if (!provider) {
      setStatus('error');
      setErrorMessage('Authentication session expired. Please try again.');
      return;
    }

    // Validate provider is valid
    if (provider !== 'google' && provider !== 'github') {
      setStatus('error');
      setErrorMessage('Invalid authentication provider');
      return;
    }

    // Exchange authorization code for tokens
    const exchangeCode = async () => {
      try {
        await handleCallback(code, provider);
        setStatus('success');
        // Brief success message before redirect (matches /auth/verify pattern)
        setTimeout(() => {
          router.push('/');
        }, 2000);
      } catch (err) {
        setStatus('error');
        // Handle specific error types
        if (err instanceof Error) {
          if (err.message.includes('conflict') || err.message.includes('already registered')) {
            setErrorMessage(err.message);
          } else if (err.message.includes('network') || err.message.includes('fetch')) {
            setErrorMessage('Connection error. Please try again.');
          } else {
            setErrorMessage(err.message || 'Authentication failed');
          }
        } else {
          setErrorMessage('Authentication failed. Please try again.');
        }
      }
    };

    exchangeCode();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Loading state
  if (status === 'loading' || isLoading) {
    return (
      <motion.div
        className="text-center space-y-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <motion.div
          className="w-16 h-16 mx-auto rounded-full bg-accent/10 flex items-center justify-center"
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
        >
          <Loader2 className="w-8 h-8 text-accent" />
        </motion.div>

        <h2 className="text-xl font-semibold text-foreground">
          Completing sign in...
        </h2>

        <p className="text-muted-foreground">
          Please wait while we verify your account.
        </p>
      </motion.div>
    );
  }

  // Success state
  if (status === 'success') {
    return (
      <motion.div
        className="text-center space-y-4"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
      >
        <motion.div
          className="w-16 h-16 mx-auto rounded-full bg-green-500/10 flex items-center justify-center"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', delay: 0.1 }}
        >
          <Check className="w-8 h-8 text-green-500" />
        </motion.div>

        <h2 className="text-xl font-semibold text-foreground">
          You&apos;re signed in!
        </h2>

        <p className="text-muted-foreground">
          Redirecting you to the dashboard...
        </p>
      </motion.div>
    );
  }

  // Error state
  return (
    <motion.div
      className="text-center space-y-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <motion.div
        className="w-16 h-16 mx-auto rounded-full bg-red-500/10 flex items-center justify-center"
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring' }}
      >
        <X className="w-8 h-8 text-red-500" />
      </motion.div>

      <h2 className="text-xl font-semibold text-foreground">
        Sign in failed
      </h2>

      <p className="text-muted-foreground">
        {errorMessage || authError || 'An error occurred during authentication.'}
      </p>

      <Button onClick={() => router.push('/auth/signin')} className="mt-4">
        Try again
      </Button>
    </motion.div>
  );
}

export default function CallbackPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <Suspense
          fallback={
            <div className="text-center">
              <Loader2 className="w-8 h-8 mx-auto text-accent animate-spin" />
            </div>
          }
        >
          <CallbackContent />
        </Suspense>
      </div>
    </div>
  );
}
