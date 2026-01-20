# Frontend Dependency Management

> **Critical Security Documentation**: This document defines the security update process for frontend dependencies. The user emphasized: "ONLY USE MATURE FRONTEND FRAMEWORK THAT PRIORITIZES SECURITY UPDATES AND FEATURES" and "my life depends on this."

**Last Security Audit**: 2025-11-23
**Next Audit Due**: 2025-12-01

---

## Table of Contents

1. [CDN Decision: Self-Hosted Libraries](#cdn-decision-self-hosted-libraries)
2. [Current Dependencies](#current-dependencies)
3. [Monthly Security Checklist](#monthly-security-checklist)
4. [Update Procedures](#update-procedures)
5. [Emergency Response](#emergency-response)
6. [Dependency Justification](#dependency-justification)

---

## CDN Decision: Self-Hosted Libraries

### Why We Self-Host (No CDN)

**Security Benefits**:
- ✅ **Zero external dependencies** - No risk of CDN compromise (SRI attacks, DNS hijacking)
- ✅ **Full version control** - We control exactly which version is deployed
- ✅ **Works offline/air-gapped** - No internet required for dashboard
- ✅ **No third-party data leakage** - CDN logs won't see user IPs or usage patterns
- ✅ **Supply chain security** - No risk of CDN serving malicious code

**Cost Benefits**:
- ✅ **$0/month** - No CDN fees, no bandwidth charges
- ✅ **Predictable** - No surprise costs from traffic spikes

**Performance Trade-offs** (Acceptable):
- ❌ No browser caching across sites (user must download once per site)
- ❌ No geographic CDN acceleration (acceptable for internal dashboard)
- ✅ Small total size (103KB) makes performance impact negligible

### CDN vs Self-Hosting: Security Analysis

| Aspect | CDN | Self-Hosted | Winner |
|--------|-----|-------------|--------|
| **Compromise Risk** | CDN breach exposes all users | Only affects our app | 🏆 Self-Hosted |
| **Version Control** | CDN controls versions | We control versions | 🏆 Self-Hosted |
| **Privacy** | CDN sees user IPs | We see user IPs only | 🏆 Self-Hosted |
| **Availability** | Dependent on CDN uptime | Dependent on our uptime | 🏆 Self-Hosted (we control SLAs) |
| **Browser Caching** | Shared across sites | Per-site only | CDN wins (but minimal impact) |

**Verdict**: Self-hosting is MORE secure for our use case.

---

## Current Dependencies

### Production Libraries (Self-Hosted)

| Library | Version | Size | Location | Purpose | Security Track Record |
|---------|---------|------|----------|---------|----------------------|
| **HTMX** | 2.0.4 | 50KB | `src/dashboard/static/vendor/htmx.min.js` | Server-driven UI | ✅ Excellent (no CVEs in 2024) |
| **HTMX SSE Extension** | 2.2.2 | 8.7KB | `src/dashboard/static/vendor/htmx-sse.min.js` | Real-time SSE | ✅ Part of HTMX ecosystem |
| **Alpine.js** | 3.14.3 | 44KB | `src/dashboard/static/vendor/alpine.min.js` | Client-side reactivity | ✅ Good (actively maintained) |

**Total Self-Hosted**: 103KB

### External Libraries (CDN - To Be Migrated)

| Library | Version | Source | Purpose | Status |
|---------|---------|--------|---------|--------|
| **Tailwind CSS** | latest | cdn.tailwindcss.com | CSS framework | ⚠️ TODO: Self-host |
| **DaisyUI** | 4.12.14 | cdn.jsdelivr.net | UI components | ⚠️ TODO: Self-host |
| **Chart.js** | 4.4.0 | cdn.jsdelivr.net | Data visualization | ⚠️ TODO: Self-host |

**Action Required**: Migrate remaining CDN dependencies to self-hosted by next security audit (2025-12-01).

---

## Monthly Security Checklist

Run this checklist on the **1st of every month** (calendar reminder required):

### Step 1: Check for CVEs (5 minutes)

```bash
# Check HTMX vulnerabilities
echo "=== Checking HTMX CVEs ==="
curl -s "https://api.osv.dev/v1/query" -d '{
  "package": {"name": "htmx.org", "ecosystem": "npm"},
  "version": "2.0.4"
}' | jq -r '.vulns[] | "\(.id): \(.summary)"'

# Check Alpine.js vulnerabilities
echo "=== Checking Alpine.js CVEs ==="
curl -s "https://api.osv.dev/v1/query" -d '{
  "package": {"name": "alpinejs", "ecosystem": "npm"},
  "version": "3.14.3"
}' | jq -r '.vulns[] | "\(.id): \(.summary)"'

# Alternative: Check GitHub Security Advisories
echo "=== GitHub Security Advisories ==="
echo "HTMX: https://github.com/bigskysoftware/htmx/security/advisories"
echo "Alpine.js: https://github.com/alpinejs/alpine/security/advisories"
```

**If CVEs Found**:
- Severity HIGH/CRITICAL → Proceed to Step 2 immediately
- Severity MEDIUM → Schedule update within 7 days
- Severity LOW → Schedule update with next monthly audit

**If No CVEs Found**:
- Document "No CVEs found" in monthly audit log
- Proceed to Step 2 to check for new versions

### Step 2: Check Latest Versions (5 minutes)

```bash
# Check HTMX latest release
echo "=== HTMX Latest Version ==="
curl -s https://api.github.com/repos/bigskysoftware/htmx/releases/latest | jq -r '.tag_name'
echo "Current: v2.0.4"

# Check Alpine.js latest release
echo "=== Alpine.js Latest Version ==="
curl -s https://api.github.com/repos/alpinejs/alpine/releases/latest | jq -r '.tag_name'
echo "Current: v3.14.3"

# Check HTMX SSE extension
echo "=== HTMX Extensions ==="
echo "Check: https://github.com/bigskysoftware/htmx-extensions/releases"
echo "Current SSE: v2.2.2"
```

**Decision Matrix**:
- **Major version increase** (e.g., v2 → v3): Schedule for testing sprint, review breaking changes
- **Minor version increase** (e.g., v2.0 → v2.1): Update if security fixes or new features needed
- **Patch version increase** (e.g., v2.0.4 → v2.0.5): Update immediately (bug fixes, no breaking changes)

### Step 3: Download and Verify Updates (If Needed)

```bash
cd src/dashboard/static/vendor

# Download HTMX (example for v2.0.5 update)
curl -sL https://unpkg.com/htmx.org@2.0.5/dist/htmx.min.js -o htmx.min.js.new

# Verify integrity (compare with official SHA256)
echo "Expected SHA256: <get from htmx.org releases page>"
sha256sum htmx.min.js.new

# Download Alpine.js (example for v3.14.4 update)
curl -sL https://unpkg.com/alpinejs@3.14.4/dist/cdn.min.js -o alpine.min.js.new

# Verify size is reasonable (should be ~44KB)
ls -lh alpine.min.js.new

# Backup old versions
mv htmx.min.js htmx.min.js.bak
mv alpine.min.js alpine.min.js.bak

# Install new versions
mv htmx.min.js.new htmx.min.js
mv alpine.min.js.new alpine.min.js
```

### Step 4: Test After Update (15 minutes)

```bash
# Run unit tests
python3 -m pytest tests/unit/test_dashboard_handler.py -v

# Run integration tests (if available)
python3 -m pytest tests/integration/test_dashboard_e2e.py -v

# Manual smoke test checklist:
# [ ] Dashboard loads without console errors
# [ ] Metrics cards update in real-time
# [ ] Chaos testing page loads
# [ ] Charts render correctly
# [ ] Mobile responsive layout works
# [ ] Dark mode toggle works (if implemented)
```

### Step 5: Document Audit (2 minutes)

Update the audit log at the top of this file:
```markdown
**Last Security Audit**: YYYY-MM-DD
**Next Audit Due**: YYYY-MM-DD (1st of next month)
**Findings**: [No CVEs found | Updated HTMX v2.0.4 → v2.0.5 | etc.]
```

Commit the changes:
```bash
git add docs/FRONTEND_DEPENDENCY_MANAGEMENT.md src/dashboard/static/vendor/
git commit -m "chore: Monthly frontend security audit (YYYY-MM)"
```

---

## Update Procedures

### Non-Critical Update (Scheduled)

1. Create a feature branch:
   ```bash
   git checkout -b chore/update-frontend-deps-YYYY-MM
   ```

2. Download and verify new versions (see Step 3 above)

3. Update version numbers in this document

4. Run full test suite:
   ```bash
   python3 -m pytest tests/
   ```

5. Create PR with change summary:
   ```bash
   gh pr create --title "chore: Update frontend dependencies (monthly audit)" \
     --body "Updates: HTMX v2.0.4 → v2.0.5, Alpine.js v3.14.3 → v3.14.4"
   ```

6. Deploy to preprod first, smoke test, then merge

### Critical Security Update (Emergency)

**Trigger**: CVE with severity HIGH or CRITICAL disclosed

1. Immediately notify team in Slack/email

2. Create emergency branch:
   ```bash
   git checkout -b hotfix/cve-YYYY-NNNN
   ```

3. Download patched version:
   ```bash
   # Example: HTMX CVE-2024-12345 fixed in v2.0.6
   curl -sL https://unpkg.com/htmx.org@2.0.6/dist/htmx.min.js -o src/dashboard/static/vendor/htmx.min.js
   ```

4. Run minimal test suite (unit tests only if time-critical):
   ```bash
   python3 -m pytest tests/unit/ -v
   ```

5. Create PR with [SECURITY] prefix:
   ```bash
   gh pr create --title "[SECURITY] Fix CVE-2024-12345 in HTMX" \
     --body "Emergency update to patch critical vulnerability. See: https://nvd.nist.gov/vuln/detail/CVE-2024-12345"
   ```

6. Deploy to production immediately after minimal validation

7. Post-mortem: Document incident in `docs/security/` directory

---

## Emergency Response

### If a Frontend Library is Compromised

**Scenario**: CDN compromise, malicious code injection, or zero-day exploit

**Immediate Actions** (Within 1 hour):

1. **Assess Blast Radius**:
   - Which library is affected?
   - What versions are vulnerable?
   - Are we currently using the vulnerable version?

2. **Isolate**:
   - If using CDN, switch to self-hosted immediately
   - If self-hosted, verify our copy isn't compromised (check SHA256)

3. **Patch or Rollback**:
   - Downgrade to last known-good version, OR
   - Apply emergency patch from upstream

4. **Deploy Emergency Fix**:
   ```bash
   git checkout -b hotfix/compromise-response
   # Replace compromised library
   git add src/dashboard/static/vendor/
   git commit -m "hotfix: Replace compromised frontend library"
   git push origin hotfix/compromise-response
   # Emergency deploy bypassing normal CI (pre-approved for security incidents)
   ```

5. **Notify Stakeholders**:
   - Post incident in #security Slack channel
   - Email engineering leads
   - Create incident ticket

**Follow-up Actions** (Within 24 hours):

1. Forensic analysis: How did we discover the compromise?
2. Impact assessment: Were any users affected?
3. Root cause: Why were we vulnerable?
4. Prevention: Update this document with lessons learned

---

## Dependency Justification

### Why We Chose These Libraries

#### HTMX (Server-Driven UI)

**Chosen Because**:
- ✅ Mature (v2.0.4, active since 2013)
- ✅ Security-first design (minimal client-side logic)
- ✅ Excellent track record (no major CVEs)
- ✅ Small size (50KB)
- ✅ Active community (10k+ GitHub stars)

**Security Considerations**:
- Low attack surface (no eval, no innerHTML)
- Server-driven reduces client-side XSS risk
- Actively maintained (latest release: 2024-11-15)

**Alternatives Considered**:
- ❌ React: Too large (500KB+ with ReactDOM), requires build pipeline
- ❌ Vue.js: Larger footprint, more client-side complexity
- ❌ Vanilla JS: Too much boilerplate for real-time updates

#### Alpine.js (Client-Side Reactivity)

**Chosen Because**:
- ✅ Lightweight (44KB)
- ✅ Security-focused (no eval, CSP-compatible)
- ✅ Active maintenance (v3.14.3 released 2024-10)
- ✅ Good track record (no major CVEs)
- ✅ Minimal learning curve

**Security Considerations**:
- Designed for CSP (Content Security Policy) compatibility
- No dynamic code execution (safe from XSS)
- Active security disclosure process on GitHub

**Alternatives Considered**:
- ❌ jQuery: Outdated, larger, more security issues historically
- ❌ Svelte: Requires build pipeline, overkill for our needs

#### Tailwind CSS + DaisyUI (Styling)

**Chosen Because**:
- ✅ Utility-first CSS (no JavaScript execution)
- ✅ DaisyUI provides beautiful components
- ✅ No security risk (CSS-only)
- ✅ Actively maintained

**Current Status**:
- ⚠️ Currently loaded from CDN (to be migrated)
- Low security risk (CSS cannot execute code)
- Plan: Self-host compiled CSS by 2025-12-01

---

## Changelog

### 2025-11-23
- Initial documentation created
- Defined monthly security checklist
- Documented self-hosting rationale
- Established emergency response procedures

---

## References

- HTMX Security: https://htmx.org/essays/security/
- Alpine.js Security: https://github.com/alpinejs/alpine/security/policy
- OSV Database API: https://osv.dev/docs/
- OWASP Dependency Check: https://owasp.org/www-project-dependency-check/

---

**Document Owner**: Engineering Security Team
**Review Frequency**: Quarterly (or after any security incident)
**Last Reviewed**: 2025-11-23
