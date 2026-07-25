// Target: Customer Dashboard (Next.js/Amplify)
// Feature 1380: Avatar SSRF allowlist + fallback behavior.
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Avatar, isAllowedAvatarUrl } from '@/components/ui/avatar';

const GOOD = 'https://lh3.googleusercontent.com/a/ACg8ocK=s96-c';

describe('isAllowedAvatarUrl (client defense-in-depth)', () => {
  it.each([
    GOOD,
    'https://googleusercontent.com/a/x',
    'https://lh4.googleusercontent.com/x',
    'https://play-lh.googleusercontent.com/x',
    'https://LH3.GOOGLEUSERCONTENT.COM/x', // normalized
    'https://lh3.googleusercontent.com./x', // trailing-dot FQDN
  ])('accepts %s', (url) => {
    expect(isAllowedAvatarUrl(url)).toBe(true);
  });

  it.each([
    'https://evil-googleusercontent.com/x', // leading-dot boundary
    'https://googleusercontent.com.evil.com/x', // suffix trick
    'https://foo.googleusercontent.com.evil.com/x',
    'https://evil.com/googleusercontent.com/x', // path trick
    'http://lh3.googleusercontent.com/x', // non-https
    'https://googleusercontent.com@evil.com/x', // userinfo trick → host evil.com
    'https://EVIL-GOOGLEUSERCONTENT.COM/x', // uppercase lookalike
    'javascript:alert(1)',
    'not a url',
    '',
  ])('rejects %s', (url) => {
    expect(isAllowedAvatarUrl(url)).toBe(false);
  });

  it('rejects null/undefined', () => {
    expect(isAllowedAvatarUrl(null)).toBe(false);
    expect(isAllowedAvatarUrl(undefined)).toBe(false);
  });
});

describe('Avatar render', () => {
  it('renders an <img> with no-referrer for an allowlisted src', () => {
    render(<Avatar src={GOOD} name="Jane" />);
    const img = document.querySelector('img') as HTMLImageElement;
    expect(img).toBeTruthy();
    expect(img.getAttribute('src')).toBe(GOOD);
    expect(img.getAttribute('referrerpolicy')).toBe('no-referrer');
  });

  it('does NOT render an <img> for a non-allowlisted src; shows initials', () => {
    render(<Avatar src="https://evil-googleusercontent.com/x" name="Jane" />);
    expect(document.querySelector('img')).toBeNull();
    expect(screen.getByText('JA')).toBeTruthy();
  });

  it('renders initials when no src is present', () => {
    render(<Avatar name="jdoe" />);
    expect(document.querySelector('img')).toBeNull();
    expect(screen.getByText('JD')).toBeTruthy();
  });

  it('renders the generic glyph (no img, no initials) when no src and no name', () => {
    const { container } = render(<Avatar />);
    expect(container.querySelector('img')).toBeNull();
    // lucide renders an <svg>; no initials span text.
    expect(container.querySelector('svg')).toBeTruthy();
  });

  it('falls back to initials on img onError (no broken-image, fallback is not an <img>)', () => {
    render(<Avatar src={GOOD} name="Jane" />);
    const img = document.querySelector('img') as HTMLImageElement;
    expect(img).toBeTruthy();
    fireEvent.error(img);
    expect(document.querySelector('img')).toBeNull(); // swapped away, no loop
    expect(screen.getByText('JA')).toBeTruthy();
  });
});
