'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Check, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/use-auth';

function VerifyContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { verifyToken, isLoading, error } = useAuth();

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const token = searchParams.get('token');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      return;
    }

    const verify = async () => {
      try {
        await verifyToken(token);
        setStatus('success');
        // Redirect after success
        setTimeout(() => {
          router.push('/');
        }, 2000);
      } catch {
        setStatus('error');
      }
    };

    verify();
  }, [token, verifyToken, router]);

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
          Verifying your magic link...
        </h2>

        <p className="text-muted-foreground">
          Please wait while we sign you in.
        </p>
      </motion.div>
    );
  }

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
        Invalid or expired link
      </h2>

      <p className="text-muted-foreground">
        {error || 'This magic link is invalid or has expired. Please request a new one.'}
      </p>

      <Button onClick={() => router.push('/auth/signin')} className="mt-4">
        Request new link
      </Button>
    </motion.div>
  );
}

export default function VerifyPage() {
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
          <VerifyContent />
        </Suspense>
      </div>
    </div>
  );
}
