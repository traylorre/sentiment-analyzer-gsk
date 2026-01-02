# Quickstart: Fix Manifest.json 404 Error

**Feature**: 1117-fix-manifest-404
**Date**: 2026-01-01

## Verification Steps

### 1. Local Development Verification

```bash
# Navigate to frontend directory
cd frontend

# Start development server
npm run dev

# In another terminal, verify manifest is served
curl -I http://localhost:3000/manifest.json
# Expected: HTTP/1.1 200 OK
# Content-Type: application/json

# Verify manifest content
curl http://localhost:3000/manifest.json | jq .
# Expected: Valid JSON with name, short_name, icons, etc.
```

### 2. Browser DevTools Verification

1. Open Chrome/Edge DevTools (F12)
2. Go to **Network** tab
3. Reload the page
4. Search for "manifest"
5. Verify:
   - Status: **200** (not 404)
   - Type: **manifest** or **json**
   - Size: ~500 bytes

### 3. Lighthouse PWA Audit

1. Open Chrome DevTools
2. Go to **Lighthouse** tab
3. Select "Progressive Web App" category
4. Run audit
5. Verify:
   - "Web app manifest meets the installability requirements" - **PASS**

### 4. PWA Install Test

1. Open dashboard in Chrome/Edge
2. Look for install icon in address bar (+ icon)
3. Click to install
4. Verify app opens in standalone window with correct name

## Post-Deployment Verification

```bash
# After deployment to Amplify, verify production manifest
curl -I https://main.d29tlmksqcx494.amplifyapp.com/manifest.json
# Expected: HTTP/2 200

curl https://main.d29tlmksqcx494.amplifyapp.com/manifest.json | jq .
# Expected: Valid JSON manifest
```

## Troubleshooting

### manifest.json still returns 404

1. Verify file exists: `ls frontend/public/manifest.json`
2. Verify file location is correct (must be in `public/` not `src/`)
3. Check Next.js build output: `npm run build` should copy public files

### Icons not loading

1. Verify icon files exist: `ls frontend/public/icons/`
2. Check paths in manifest match actual file locations
3. Verify icon files are valid PNG format

### Cache issues after deployment

1. Clear CloudFront/CDN cache if 404 persists after deploy
2. Hard refresh browser (Ctrl+Shift+R)
3. Clear browser application cache in DevTools > Application > Clear storage

## Success Criteria Checklist

- [ ] `curl /manifest.json` returns HTTP 200
- [ ] No 404 errors in browser Network tab
- [ ] Lighthouse PWA "installability requirements" passes
- [ ] Chrome shows "Install app" option
- [ ] manifest.json loads in < 100ms (check Network tab timing)
