/**
 * SSE Proxy Route Handler (Gap 4: Same-Origin Proxy)
 *
 * Routes SSE through Next.js API route so cookies work natively (same origin).
 * This eliminates token-in-URL security issues:
 * - Token never in URL (not logged anywhere)
 * - HttpOnly cookie (XSS can't steal)
 * - Same-origin (no CORS complexity)
 * - Lambda can be private (not publicly accessible)
 *
 * Flow: Frontend -> /api/sse/stream (same origin, cookie sent) -> Lambda
 */

import { NextRequest } from 'next/server';

export const runtime = 'edge';
export const dynamic = 'force-dynamic';

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  // Cookie sent automatically (same origin)
  const token = request.cookies.get('sentiment-access-token')?.value;

  if (!token) {
    return new Response('Unauthorized', { status: 401 });
  }

  const sseUrl = process.env.SSE_LAMBDA_URL;
  if (!sseUrl) {
    console.error('SSE_LAMBDA_URL environment variable not configured');
    return new Response('SSE endpoint not configured', { status: 503 });
  }

  // Build upstream path from catch-all segments
  const upstreamPath = params.path?.join('/') || 'stream';
  const upstreamUrl = `${sseUrl}/${upstreamPath}`;

  try {
    // T067 (FR-032): Propagate X-Amzn-Trace-Id from incoming request to upstream
    // 1220 FR-011: Generate fallback if browser didn't send one
    let traceId = request.headers.get('X-Amzn-Trace-Id');
    if (!traceId) {
      const ts = Math.floor(Date.now() / 1000).toString(16);
      traceId = `Root=1-${ts}-${crypto.randomUUID().replace(/-/g, '').slice(0, 24)};Sampled=1`;
    }
    const upstreamHeaders: Record<string, string> = {
      Authorization: `Bearer ${token}`,
      Accept: 'text/event-stream',
      'X-Amzn-Trace-Id': traceId,
    };

    // Server-to-server call (can use headers)
    const upstream = await fetch(upstreamUrl, {
      headers: upstreamHeaders,
    });

    if (!upstream.ok) {
      return new Response(upstream.statusText, { status: upstream.status });
    }

    // Stream response back to client
    // T067: Expose upstream X-Amzn-Trace-Id so SSEConnection can read it (FR-033)
    const responseHeaders: Record<string, string> = {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    };
    const upstreamTraceId = upstream.headers.get('X-Amzn-Trace-Id');
    if (upstreamTraceId) {
      responseHeaders['X-Amzn-Trace-Id'] = upstreamTraceId;
    }

    return new Response(upstream.body, {
      headers: responseHeaders,
    });
  } catch (error) {
    console.error('SSE proxy error:', error);
    return new Response('SSE connection failed', { status: 502 });
  }
}
