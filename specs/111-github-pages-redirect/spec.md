# Feature 111: GitHub Pages Root Redirect

## Problem Statement

Visiting `https://traylorre.github.io/sentiment-analyzer-gsk/` returns 404 because GitHub Pages serves from root but the Interview Dashboard is in `/interview/`.

## Solution

Add a root `index.html` that redirects to `/interview/`.

## Implementation

Create `/index.html` with:
1. Meta refresh tag (works without JavaScript)
2. JavaScript redirect (faster for modern browsers)
3. Fallback link (for screen readers and edge cases)

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | Root URL redirects to /interview/ | Browser test |
| SC-002 | Redirect works without JavaScript | Disable JS and test |
| SC-003 | No 404 at root | curl -I returns 200 |
