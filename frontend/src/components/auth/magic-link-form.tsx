'use client';

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mail, ArrowRight, Check, AlertCircle } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/use-auth';
import { cn } from '@/lib/utils';

interface MagicLinkFormProps {
  className?: string;
  onSuccess?: () => void;
}

type FormState = 'idle' | 'loading' | 'success' | 'error';

export function MagicLinkForm({ className, onSuccess }: MagicLinkFormProps) {
  const [email, setEmail] = useState('');
  const [formState, setFormState] = useState<FormState>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const { requestMagicLink, isLoading } = useAuth();

  const isValidEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!isValidEmail) {
        setErrorMessage('Please enter a valid email address');
        setFormState('error');
        return;
      }

      try {
        setFormState('loading');
        setErrorMessage('');

        // In production, this would be a real captcha token
        // For now, use a placeholder
        const captchaToken = 'demo-captcha-token';

        await requestMagicLink(email, captchaToken);
        setFormState('success');
        onSuccess?.();
      } catch (error) {
        setFormState('error');
        setErrorMessage(
          error instanceof Error ? error.message : 'Failed to send magic link'
        );
      }
    },
    [email, isValidEmail, requestMagicLink, onSuccess]
  );

  if (formState === 'success') {
    return (
      <motion.div
        className={cn('text-center space-y-4', className)}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <motion.div
          className="w-16 h-16 mx-auto rounded-full bg-green-500/10 flex items-center justify-center"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', delay: 0.1 }}
        >
          <Check className="w-8 h-8 text-green-500" />
        </motion.div>

        <h3 className="text-xl font-semibold text-foreground">Check your email</h3>

        <p className="text-muted-foreground">
          We&apos;ve sent a magic link to{' '}
          <span className="font-medium text-foreground">{email}</span>
        </p>

        <p className="text-sm text-muted-foreground">
          Click the link in the email to sign in. The link expires in 15 minutes.
        </p>

        <Button
          variant="outline"
          onClick={() => {
            setFormState('idle');
            setEmail('');
          }}
          className="mt-4"
        >
          Use a different email
        </Button>
      </motion.div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-4', className)}>
      <div className="space-y-2">
        <label htmlFor="email" className="text-sm font-medium text-foreground">
          Email address
        </label>

        <div className="relative">
          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (formState === 'error') {
                setFormState('idle');
                setErrorMessage('');
              }
            }}
            placeholder="you@example.com"
            className="pl-10"
            disabled={formState === 'loading'}
            autoComplete="email"
            autoFocus
          />
        </div>
      </div>

      {/* Error message */}
      <AnimatePresence>
        {formState === 'error' && errorMessage && (
          <motion.div
            className="flex items-center gap-2 text-sm text-red-500"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{errorMessage}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <Button
        type="submit"
        className="w-full gap-2"
        disabled={!email || formState === 'loading'}
      >
        {formState === 'loading' ? (
          <>
            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            Sending...
          </>
        ) : (
          <>
            Continue with Email
            <ArrowRight className="w-4 h-4" />
          </>
        )}
      </Button>

      <p className="text-xs text-center text-muted-foreground">
        We&apos;ll send you a magic link to sign in instantly. No password required.
      </p>
    </form>
  );
}
