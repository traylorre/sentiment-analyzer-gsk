# Research: Validation Blind Spot Audit

**Feature**: 070-validation-blindspot-audit
**Date**: 2025-12-08
**Purpose**: Resolve NEEDS CLARIFICATION items and document technical decisions

## Research Questions

### RQ-001: Which SAST tool can detect py/log-injection and py/clear-text-logging-sensitive-data locally?

**Context**: CodeQL detects these patterns in CI but nothing detects them locally.

**Findings**:

| Tool | py/log-injection | py/clear-text-logging | Execution Time | Notes |
|------|-----------------|----------------------|----------------|-------|
| Bandit | Partial | NO | 5-15s | AST-only, no taint tracking |
| Semgrep | **YES** | **YES** | 15-45s | Taint analysis with community rules |
| Local CodeQL | YES | YES | 120-300s | Too slow for pre-commit |
| Pyre/Pysa | YES (config) | YES (config) | 60-180s | Complex setup required |
| pylint | NO | NO | 15-30s | Not a security tool |

**Decision**: Use Semgrep as primary SAST tool for local validation.

**Rationale**:
- Detects both target vulnerability patterns via taint tracking
- Completes in <60s (meets NFR-001)
- Free and open source
- Active community ruleset for OWASP patterns
- Pre-commit and Makefile integration available

**Alternatives Rejected**:
- Local CodeQL: Too slow (2-5 min), overkill when CI already runs it
- Pyre/Pysa: Complex configuration, higher maintenance burden
- Bandit alone: Misses clear-text logging patterns entirely

---

### RQ-002: Should Bandit be added in addition to Semgrep?

**Context**: Bandit is faster but less comprehensive than Semgrep.

**Decision**: Yes, use two-tier approach.

**Rationale**:
- Bandit (5-15s): Fast pre-commit feedback on common patterns
- Semgrep (15-45s): Comprehensive `make sast` for deeper analysis
- Combined coverage exceeds either tool alone
- Bandit catches ~30-40% of CodeQL findings instantly

**Integration Strategy**:
```
Layer         | Tool    | When          | Blocking
------------- | ------- | ------------- | --------
Pre-commit    | Bandit  | Every commit  | HIGH only
Make validate | Semgrep | Before push   | HIGH+MEDIUM
CI            | CodeQL  | After push    | All
```

---

### RQ-003: How should vulnerability remediation be approached?

**Context**: 3 existing HIGH-severity vulnerabilities need fixing.

**Findings** (from CodeQL alerts):

1. **py/clear-text-logging-sensitive-data** (1 instance)
   - Location: Logging module
   - Issue: Sensitive data written to logs without redaction
   - Fix: Use redaction function before logging

2. **py/log-injection** (2 instances)
   - Location: Request handling code
   - Issue: User-controlled data written to logs without sanitization
   - Fix: Sanitize/escape user input before logging

**Decision**: Fix all 3 vulnerabilities as part of this feature.

**Remediation Patterns**:

```python
# Pattern 1: Redact sensitive data
# BAD
logger.info(f"API key: {api_key}")

# GOOD
logger.info(f"API key: {redact(api_key)}")

# Pattern 2: Sanitize user input
# BAD
logger.info(f"User input: {user_input}")

# GOOD
logger.info(f"User input: {sanitize_log_input(user_input)}")
```

**Rationale**: Fixing existing vulnerabilities proves the tooling works and demonstrates the feedback loop (catch locally what CI would have caught).

---

### RQ-004: What severity levels should block commits?

**Context**: Need to balance security strictness with developer friction.

**Decision**: Block HIGH and MEDIUM; report LOW.

**Rationale** (per user clarification):
- HIGH/MEDIUM: Significant security risk, must be fixed before commit
- LOW: Awareness-level findings, can be addressed later
- Can tighten to block LOW in future if needed

**Implementation**:
```yaml
# Bandit in pre-commit
args: [--severity-level=medium, --exit-zero-if-skipped]

# Semgrep in Makefile
semgrep --severity ERROR --severity WARNING --error
```

---

### RQ-005: How to handle false positives and exclusions?

**Context**: SAST tools may flag legitimate code patterns.

**Decision**: Use inline comments and configuration files for exclusions.

**Exclusion Mechanisms**:

1. **Bandit**: `# nosec` comment or `.bandit` config file
2. **Semgrep**: `# nosemgrep` comment or `.semgrepignore` file
3. **Documentation**: All exclusions must be documented with justification

**Governance**:
- Exclusions require code review approval
- Must include comment explaining why exclusion is safe
- Periodic audit of exclusions recommended

---

## Resolved NEEDS CLARIFICATION Items

| Item | Resolution |
|------|------------|
| Tool selection | Semgrep + Bandit (two-tier) |
| Severity blocking | HIGH+MEDIUM block; LOW reports |
| Existing vulnerabilities | Fix as part of feature |
| Performance target | <60s total (Bandit 5-15s, Semgrep 15-45s) |

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| semgrep | >=1.50.0 | Primary SAST with taint analysis |
| bandit | >=1.7.0 | Fast Python security linter |
| pre-commit | >=3.0.0 | Git hooks framework (existing) |

## References

- [Semgrep Python Rules](https://semgrep.dev/p/python)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [OWASP Top 10](https://owasp.org/Top10/)
- [CodeQL Python Queries](https://codeql.github.com/codeql-query-help/python/)
