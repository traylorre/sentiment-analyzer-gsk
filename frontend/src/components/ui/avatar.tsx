'use client';

// Target: Customer Dashboard (Next.js/Amplify)
// Feature 1380: shared, SSRF-safe avatar. Hot-link only — the browser fetches
// Google directly; we never proxy/fetch the URL server-side. Rendered ONLY as
// an <img src> (auto-escaped by React), never href/innerHTML.

import { useState } from 'react';
import { User } from 'lucide-react';
import { cn } from '@/lib/utils';

const AVATAR_ALLOWED_HOST = 'googleusercontent.com';

/**
 * Client-side defense-in-depth host allowlist. Mirrors the backend
 * `_validate_avatar_url` exact-suffix rule: https-only, and the parsed hostname
 * is exactly `googleusercontent.com` or ends with `.googleusercontent.com`
 * (the leading dot is load-bearing). The backend is authoritative; this is a
 * second gate so a bad value can never reach an <img src>.
 */
export function isAllowedAvatarUrl(src: string | undefined | null): boolean {
  if (!src) return false;
  let url: URL;
  try {
    url = new URL(src);
  } catch {
    return false;
  }
  if (url.protocol !== 'https:') return false;
  const host = url.hostname.replace(/\.$/, '').toLowerCase();
  return host === AVATAR_ALLOWED_HOST || host.endsWith('.' + AVATAR_ALLOWED_HOST);
}

function initialsFrom(name: string | undefined): string | null {
  if (!name) return null;
  const trimmed = name.trim();
  if (!trimmed) return null;
  // First 1-2 characters, uppercased. Works with a masked local-part (e.g. "j***" -> "J").
  return trimmed.slice(0, 2).toUpperCase();
}

interface AvatarProps {
  src?: string | null;
  name?: string;
  /** Diameter in pixels (trigger ~32, header ~40). */
  size?: number;
  className?: string;
}

export function Avatar({ src, name, size = 32, className }: AvatarProps) {
  const [failed, setFailed] = useState(false);

  const dims = { width: size, height: size };
  const containerCls = cn(
    'rounded-full overflow-hidden bg-accent/20 flex items-center justify-center shrink-0',
    className
  );

  const showImage = !failed && isAllowedAvatarUrl(src);

  if (showImage) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- hot-link, no next/image optimizer (SSRF surface, R4)
      <img
        src={src as string}
        alt=""
        aria-hidden="true"
        width={size}
        height={size}
        // No cookies/credentials leave to the image host; no app path leaks.
        referrerPolicy="no-referrer"
        crossOrigin="anonymous"
        onError={() => setFailed(true)}
        className={cn('object-cover rounded-full shrink-0', className)}
        style={dims}
      />
    );
  }

  const initials = initialsFrom(name);

  // Fallback is text/glyph — NEVER an <img> — so a broken URL cannot loop.
  return (
    <div className={containerCls} style={dims} aria-hidden="true">
      {initials ? (
        <span className="font-medium text-accent" style={{ fontSize: size * 0.4 }}>
          {initials}
        </span>
      ) : (
        <User className="text-accent" style={{ width: size * 0.5, height: size * 0.5 }} />
      )}
    </div>
  );
}
