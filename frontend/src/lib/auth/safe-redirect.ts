/**
 * Feature 1394: Open-redirect guard for the post-sign-in `?redirect=` target.
 *
 * ProtectedRoute bounces gated routes to `/auth/signin?redirect=<path>`. After
 * sign-in we return the user to that path — but only when it is a same-origin,
 * absolute *internal* path. Anything protocol-relative (`//evil.com`), a full
 * URL (`https://evil.com`), or a value not rooted at `/` (`javascript:…`,
 * relative segments) falls back to the dashboard root so an attacker-supplied
 * `redirect` param can never bounce the user off-site.
 */
export function safeInternalPath(
  raw: string | null | undefined,
  fallback = '/',
): string {
  if (typeof raw !== 'string' || raw.length === 0) return fallback;
  // CRITICAL: browsers (and Next's router via `new URL`) strip ASCII tab/CR/LF
  // and other C0 control chars from a URL *before* resolving it. A prefix check
  // on the raw string is therefore bypassable: `/\t/evil.com` passes a
  // `startsWith('//')` test but is parsed as `//evil.com` and navigates
  // off-origin. Strip those control chars FIRST so every check below — and the
  // eventual `router.push` — sees the same value.
  const cleaned = raw.replace(/[\u0000-\u001F\u007F]/g, '');
  // Must be a rooted internal path (rejects `https://…`, `javascript:…`, and
  // any relative value), and not protocol-relative / its backslash variant.
  if (!cleaned.startsWith('/')) return fallback;
  if (cleaned.startsWith('//') || cleaned.startsWith('/\\')) return fallback;
  // Belt-and-suspenders: resolve against a sentinel origin and require the
  // result stays same-origin. Catches any residual smuggling the prefix checks
  // miss (WHATWG treats `\` as `/` for special schemes, etc.). Return only
  // path+query+hash so the caller can never be sent off-site.
  try {
    const url = new URL(cleaned, 'https://internal.invalid');
    if (url.origin !== 'https://internal.invalid') return fallback;
    const path = `${url.pathname}${url.search}${url.hash}`;
    // Dot-segment normalization (`/..//evil.com`) can collapse the pathname to a
    // leading `//`, which is authority-bearing when the caller re-parses it —
    // the resolved-origin check above guards the wrong value. Re-resolve the
    // EXACT string we are about to return (the same value the caller passes to
    // `router.push`) and require it, too, stays same-origin.
    if (path.startsWith('//') || path.startsWith('/\\')) return fallback;
    if (new URL(path, 'https://internal.invalid').origin !== 'https://internal.invalid') {
      return fallback;
    }
    return path;
  } catch {
    return fallback;
  }
}
