'use client';

import { motion } from 'framer-motion';
import { LayoutDashboard } from 'lucide-react';
import { MagicLinkForm } from '@/components/auth/magic-link-form';
import { OAuthButtons, AuthDivider } from '@/components/auth/oauth-buttons';
import { Card } from '@/components/ui/card';

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <motion.div
        className="w-full max-w-md"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center">
            <LayoutDashboard className="w-5 h-5 text-background" />
          </div>
          <span className="text-2xl font-bold text-foreground">Sentiment</span>
        </div>

        {/* Card */}
        <Card className="p-6 space-y-6">
          <div className="text-center space-y-2">
            <h1 className="text-2xl font-bold text-foreground">Welcome back</h1>
            <p className="text-muted-foreground">
              Sign in to access your sentiment dashboard
            </p>
          </div>

          {/* OAuth buttons */}
          <OAuthButtons />

          {/* Divider */}
          <AuthDivider />

          {/* Magic link form */}
          <MagicLinkForm />
        </Card>

        {/* Footer */}
        <p className="text-center text-xs text-muted-foreground mt-6">
          By signing in, you agree to our{' '}
          <a href="/terms" className="text-accent hover:underline">
            Terms of Service
          </a>{' '}
          and{' '}
          <a href="/privacy" className="text-accent hover:underline">
            Privacy Policy
          </a>
        </p>

        {/* Anonymous option */}
        <div className="text-center mt-4">
          <a
            href="/"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Continue as guest
          </a>
        </div>
      </motion.div>
    </div>
  );
}
