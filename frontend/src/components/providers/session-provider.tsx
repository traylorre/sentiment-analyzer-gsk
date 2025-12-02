'use client';

import { useSessionInit } from '@/hooks/use-session-init';

interface SessionProviderProps {
  children: React.ReactNode;
  /**
   * Optional loading component to show while session initializes.
   * Defaults to a minimal loading indicator.
   */
  loadingComponent?: React.ReactNode;
  /**
   * Optional error component to show if session initialization fails.
   * Receives the error message as a prop.
   */
  errorComponent?: React.ReactNode;
  /**
   * Whether to show loading state. Set to false to render children immediately
   * while session initializes in background.
   * @default true
   */
  showLoading?: boolean;
}

/**
 * Provider component for automatic session initialization (Feature 014, FR-003).
 *
 * Wraps the application to ensure a session (anonymous or authenticated) exists
 * before rendering children. This enables:
 * - Automatic anonymous session creation on app load
 * - Cross-tab session sharing via localStorage
 * - Seamless upgrade from anonymous to authenticated
 *
 * Usage in layout.tsx:
 * ```tsx
 * export default function RootLayout({ children }) {
 *   return (
 *     <html>
 *       <body>
 *         <Providers>
 *           <SessionProvider>
 *             {children}
 *           </SessionProvider>
 *         </Providers>
 *       </body>
 *     </html>
 *   );
 * }
 * ```
 */
export function SessionProvider({
  children,
  loadingComponent,
  errorComponent,
  showLoading = true,
}: SessionProviderProps) {
  const { isInitializing, isError, error, isReady } = useSessionInit();

  // Show loading state while session initializes
  if (showLoading && isInitializing) {
    return (
      <>
        {loadingComponent || (
          <div className="flex items-center justify-center min-h-screen">
            <div className="animate-pulse text-muted-foreground">
              Initializing session...
            </div>
          </div>
        )}
      </>
    );
  }

  // Show error state if session initialization failed
  if (isError && errorComponent) {
    return <>{errorComponent}</>;
  }

  // Render children once session is ready (or immediately if showLoading=false)
  return <>{children}</>;
}

/**
 * Hook to check session readiness from child components.
 * Use this to conditionally render UI that requires an active session.
 */
export { useSessionInit } from '@/hooks/use-session-init';
