# Frontend Dependency Management

**Decision Date**: 2025-11-24
**Status**: Self-Hosted Libraries (No CDN Dependencies)
**Security Impact**: High (eliminates external dependencies)

---

## CDN Decision: Self-Hosted Libraries

### Why We Self-Host (No CDN)

**Security Benefits**:
- ✅ **Zero external dependencies** - No risk of CDN compromise
- ✅ **Full version control** - We control exactly which version is deployed
- ✅ **Works offline/air-gapped** - No internet required for dashboard
- ✅ **No third-party data leakage** - CDN logs won't see user IPs

**Cost Benefits**:
- ✅ **$0/month** - No CDN fees
- ✅ **Predictable** - No surprise bandwidth charges

**Trade-offs**:
- ❌ **Manual updates required** - Must monitor CVEs and update libraries
- ❌ **+103KB Lambda package** - Within 50MB limit (acceptable)
- ❌ **Slower initial load** - No cross-site caching benefit

---

## Current Self-Hosted Libraries

| Library | Version | Size | Location | Purpose |
|---------|---------|------|----------|---------|
| HTMX | 2.0.4 | 50KB | `src/dashboard/static/vendor/htmx.min.js` | Server-driven UI interactions |
| HTMX SSE | 2.2.2 | 8.7KB | `src/dashboard/static/vendor/htmx-sse.min.js` | Real-time server-sent events |
| Alpine.js | 3.14.3 | 44KB | `src/dashboard/static/vendor/alpine.min.js` | Lightweight reactivity |

**Total**: 103KB (acceptable for feature set)

**External CDNs Still Used** (to be replaced in production):
- Tailwind CSS: ~70KB (will be replaced with compiled CSS in production)
- DaisyUI: ~20KB (bundled with Tailwind build)
- Chart.js: ~200KB (consider self-hosting or replacing with lighter alternative)

---

## Security Update Checklist (Monthly)

Run this checklist on the **1st of every month** to ensure frontend libraries are up-to-date:

### Step 1: Check for CVEs

```bash
# Check Snyk vulnerability database
curl -s "https://snyk.io/vuln/npm:htmx.org" | grep -i "vulnerability"
curl -s "https://snyk.io/vuln/npm:alpinejs" | grep -i "vulnerability"

# Check GitHub Security Advisories
gh api repos/bigskysoftware/htmx/security-advisories
gh api repos/alpinejs/alpine/security-advisories
```

### Step 2: Check Latest Versions

```bash
# HTMX
curl -s https://api.github.com/repos/bigskysoftware/htmx/releases/latest | jq -r '.tag_name'

# Alpine.js
curl -s https://api.github.com/repos/alpinejs/alpine/releases/latest | jq -r '.tag_name'
```

### Step 3: Download Updates (If CVEs Found)

```bash
cd src/dashboard/static/vendor

# Update HTMX (replace version as needed)
curl -sL https://unpkg.com/htmx.org@2.0.5/dist/htmx.min.js -o htmx.min.js.new
mv htmx.min.js.new htmx.min.js

# Update HTMX SSE extension
curl -sL https://unpkg.com/htmx-ext-sse@2.2.3/sse.js -o htmx-sse.min.js.new
mv htmx-sse.min.js.new htmx-sse.min.js

# Update Alpine.js
curl -sL https://cdn.jsdelivr.net/npm/alpinejs@3.14.4/dist/cdn.min.js -o alpine.min.js.new
mv alpine.min.js.new alpine.min.js

cd -
```

### Step 4: Test Locally

```bash
# Test dashboard loads without errors
pytest tests/integration/test_e2e_lambda_invocation_preprod.py -k dashboard

# Manual testing checklist:
# - [ ] Dashboard loads without JavaScript errors (check browser console)
# - [ ] Metrics cards update correctly
# - [ ] Charts render properly
# - [ ] Dark mode toggle works
# - [ ] Real-time SSE updates work
# - [ ] Search and filter work
# - [ ] Mobile responsive layout works
```

### Step 5: Deploy to Preprod

```bash
git add src/dashboard/static/vendor/
git commit -m "security: Update frontend libraries to patch CVE-YYYY-XXXXX"
git push origin main
```

### Step 6: Document Update

Update this file with new versions:

```markdown
## Update History

| Date | Library | Old Version | New Version | Reason |
|------|---------|-------------|-------------|--------|
| 2025-11-24 | HTMX | N/A | 2.0.4 | Initial self-hosting |
| 2025-11-24 | Alpine.js | N/A | 3.14.3 | Initial self-hosting |
| 2025-11-24 | HTMX SSE | N/A | 2.2.2 | Initial self-hosting |
```

---

## Known CVEs (Tracking)

### HTMX
- **No known CVEs** as of 2025-11-24
- Snyk security grade: **A+**
- Last checked: 2025-11-24

### Alpine.js
- **No known CVEs** as of 2025-11-24
- Snyk security grade: **A+**
- Last checked: 2025-11-24

### Rejected Libraries (DO NOT USE)

| Library | Reason | CVE Reference |
|---------|--------|---------------|
| Svelte | XSS vulnerability in `@html` directive | CVE-2024-45047 |

---

## Production Build (Future Enhancement)

**Current State**: Using Tailwind CSS CDN (acceptable for demo/preprod)

**Production Optimization** (implement before prod deployment):

```bash
# Install Tailwind CLI (no Node.js required)
cd src/dashboard
curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
chmod +x tailwindcss-linux-x64

# Build optimized CSS (includes only used classes)
./tailwindcss-linux-x64 -i static/input.css -o static/tailwind.min.css --minify

# Result: ~10KB instead of 70KB CDN script
```

**Update `index.html`**:
```html
<!-- Development (CDN) -->
<script src="https://cdn.tailwindcss.com"></script>

<!-- Production (self-hosted) -->
<link href="/static/tailwind.min.css" rel="stylesheet">
```

---

## Update History

| Date | Library | Old Version | New Version | Reason |
|------|---------|-------------|-------------|--------|
| 2025-11-24 | HTMX | N/A | 2.0.4 | Initial self-hosting |
| 2025-11-24 | Alpine.js | N/A | 3.14.3 | Initial self-hosting |
| 2025-11-24 | HTMX SSE | N/A | 2.2.2 | Initial self-hosting |

---

## References

- [HTMX Security](https://htmx.org/security/)
- [Alpine.js Security](https://alpinejs.dev/advanced/security)
- [Snyk Vulnerability Database](https://snyk.io/vuln/)
- [GitHub Security Advisories](https://github.com/advisories)
- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)

---

**Next Security Review**: 2025-12-01
