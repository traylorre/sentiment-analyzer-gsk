# Implementation Tasks: OAuth Callback Route Handler

**Branch**: `1192-oauth-callback-route` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Task Summary

| ID | Task | Status | Estimate |
|----|------|--------|----------|
| T01 | Update auth-store to store provider in sessionStorage | Pending | S |
| T02 | Create callback page component | Pending | M |
| T03 | Add error handling for missing provider | Pending | S |
| T04 | Add unit tests for callback page | Pending | M |
| T05 | Manual E2E verification | Pending | S |

## Tasks

### T01: Update auth-store to store provider in sessionStorage

**File**: `frontend/src/stores/auth-store.ts`

**Changes**:
1. In `signInWithOAuth`, before redirecting to OAuth URL, store provider in sessionStorage:
   ```typescript
   sessionStorage.setItem('oauth_provider', provider);
   ```

**Acceptance Criteria**:
- [ ] Provider is stored before redirect
- [ ] Storage key is `oauth_provider`
- [ ] No other auth data stored (security requirement)

---

### T02: Create callback page component

**File**: `frontend/src/app/auth/callback/page.tsx` (NEW)

**Implementation**:
1. Create page following `/auth/verify/page.tsx` pattern
2. Extract URL params: `code`, `state`, `error`
3. Retrieve provider from sessionStorage
4. Clear sessionStorage immediately after retrieval
5. Call `handleCallback(code, provider)` from useAuth hook
6. Display loading → success → redirect to `/`
7. Display error states with retry button

**Component Structure**:
```typescript
'use client';

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
  const { handleCallback, isLoading, error } = useAuth();

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const code = searchParams.get('code');
  const errorParam = searchParams.get('error');

  useEffect(() => {
    // Handle provider denial
    if (errorParam) {
      setStatus('error');
      setErrorMessage('Authentication was cancelled');
      return;
    }

    // Get and clear stored provider
    const provider = sessionStorage.getItem('oauth_provider') as OAuthProvider | null;
    sessionStorage.removeItem('oauth_provider');

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

    const exchange = async () => {
      try {
        await handleCallback(code, provider);
        setStatus('success');
        setTimeout(() => router.push('/'), 2000);
      } catch (err) {
        setStatus('error');
        setErrorMessage(err instanceof Error ? err.message : 'Authentication failed');
      }
    };

    exchange();
  }, [code, errorParam, handleCallback, router]);

  // Render loading/success/error states (see Phase 2)
}

export default function CallbackPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <Suspense fallback={<Loader2 className="w-8 h-8 mx-auto text-accent animate-spin" />}>
          <CallbackContent />
        </Suspense>
      </div>
    </div>
  );
}
```

**Acceptance Criteria**:
- [ ] Page renders at `/auth/callback`
- [ ] Extracts code, state, error from URL
- [ ] Retrieves and clears provider from sessionStorage
- [ ] Calls handleCallback with code and provider
- [ ] Shows loading spinner immediately
- [ ] Redirects to `/` on success after 2s
- [ ] Shows error with retry button on failure

---

### T03: Add error handling for missing provider

**File**: `frontend/src/app/auth/callback/page.tsx`

**Error Scenarios**:
1. `error` param in URL → "Authentication was cancelled"
2. Missing `code` param → "Invalid callback: missing authorization code"
3. Missing provider in sessionStorage → "Authentication session expired. Please try again."
4. Backend error → Display error message from response
5. Network error → "Connection error. Please try again."
6. Conflict response → "This email is already registered..."

**Acceptance Criteria**:
- [ ] Each error scenario has distinct, helpful message
- [ ] Retry button navigates to `/auth/signin`
- [ ] Error state uses red X icon (matching verify page)

---

### T04: Add unit tests for callback page

**File**: `frontend/tests/unit/app/auth/callback.test.tsx` (NEW)

**Test Cases**:
1. `renders loading state initially`
2. `extracts code from URL params`
3. `retrieves provider from sessionStorage`
4. `clears sessionStorage after retrieval`
5. `calls handleCallback with correct params`
6. `shows success state after successful callback`
7. `redirects to / after success`
8. `shows error when code is missing`
9. `shows error when provider is missing`
10. `shows error when provider denied (error param)`
11. `shows error when handleCallback fails`
12. `retry button navigates to signin`

**Acceptance Criteria**:
- [ ] All 12 test cases pass
- [ ] Tests mock useAuth hook
- [ ] Tests mock useSearchParams
- [ ] Tests mock sessionStorage

---

### T05: Manual E2E verification

**Steps**:
1. Start frontend dev server
2. Navigate to `/auth/signin`
3. Click "Continue with Google"
4. Complete Google OAuth flow
5. Verify callback page shows loading then redirects to `/`
6. Verify user is authenticated

**Acceptance Criteria**:
- [ ] Google OAuth flow completes successfully
- [ ] GitHub OAuth flow completes successfully (if configured)
- [ ] Error scenarios display correct messages
- [ ] No console errors during flow

## Dependencies

- **Requires**: Existing `useAuth` hook with `handleCallback` function
- **Requires**: Existing `authApi.exchangeOAuthCode` API function
- **Blocked by**: None
- **Blocks**: Feature 1193 (OAuth state/CSRF validation)

## Notes

- This feature uses sessionStorage for provider as a temporary solution
- Feature 1193 will add proper state-based provider detection with CSRF protection
- sessionStorage is chosen over localStorage for better cross-tab isolation
- The redirect_uri and state parameters are not yet sent to backend (Feature 1193 scope)
