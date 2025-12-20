# Methodology Violation Report: MVR-001

**Date**: 2025-12-08
**Feature**: 070-validation-blindspot-audit
**Phase Violated**: `/speckit.specify`
**Severity**: HIGH - Template methodology flaw

## Summary

During execution of `/speckit.specify`, the specification phase leaked implementation details that belong exclusively to the `/speckit.plan` phase. This violation was caught by human review, not by any automated check.

## Violation Details

### What Happened

The initial spec.md (Revision 1) contained:

1. **Specific tool names**:
   - "Bandit, Semgrep, or local CodeQL"
   - "pip-audit", "tfsec", "detect-secrets", "gitleaks", "ruff"

2. **Implementation mechanisms**:
   - "`make validate`", "`make security`", "`make install-tools`"
   - "pre-commit hooks"
   - "pre-push hook"

3. **Specific file paths**:
   - "`src/lambdas/shared/secrets.py`"
   - "`src/lambdas/dashboard/ohlc.py`"

4. **Configuration references**:
   - "Makefile integration"
   - "Pre-commit hook updates"
   - "README/Makefile"

### Why It Matters

1. **Phase Boundary Violation**: Specifications should describe WHAT and WHY, never HOW
2. **Premature Solution Lock-in**: Naming tools constrains planning phase options
3. **Template Methodology Failure**: The violation passed the 16-item quality checklist
4. **No Automated Detection**: Only human review caught the violation

## Root Cause Analysis

### Immediate Cause

The agent investigated the codebase to understand the problem (appropriate) but then included discovered implementation details in the specification (inappropriate).

### Contributing Factors

1. **Template ambiguity**: The spec template says "technology-agnostic" but doesn't define what that means for problem statements
2. **Checklist gap**: Checklist item "No implementation details" lacks specific examples of what constitutes implementation details
3. **Evidence vs. Implementation conflation**: File paths are evidence but also implementation details - no guidance on how to reference evidence without leaking implementation
4. **No automated enforcement**: No tooling validates spec content against phase boundaries

### Systemic Issue

The `/speckit.specify` command prompt allows investigation of the codebase. Investigation naturally discovers implementation details. No guardrail prevents those details from appearing in the output.

## Artifacts for Constitution Overhaul

### Finding 1: Checklist needs explicit examples

Current checklist item:
```
- [ ] No implementation details (languages, frameworks, APIs)
```

Proposed enhancement:
```
- [ ] No implementation details leak into specification
  - No tool names (Bandit, CodeQL, pytest, etc.)
  - No file paths (src/..., tests/..., etc.)
  - No command names (make X, npm X, etc.)
  - No configuration files (.pre-commit-config.yaml, Makefile, etc.)
  - Evidence references use descriptions, not paths ("a logging module" not "src/shared/secrets.py")
```

### Finding 2: Spec template needs anti-pattern examples

Add to spec template:
```markdown
### Anti-Patterns (DO NOT include)

❌ "Add Bandit to make security target"
✅ "Local validation must detect security vulnerabilities"

❌ "Update .pre-commit-config.yaml"
✅ "Automated checks must block commits with vulnerabilities"

❌ "Fix src/lambdas/shared/secrets.py line 226"
✅ "3 HIGH-severity vulnerabilities exist in the codebase"
```

### Finding 3: Phase boundary automation needed

New validator for `/speckit.specify` output:

**Blocked Patterns**:
- File paths matching `src/`, `tests/`, `infrastructure/`, etc.
- Tool names from common tool list
- Command patterns (`make `, `npm `, `pip `, `git `)
- Configuration file extensions (`.yaml`, `.toml`, `.json` in filenames)

### Finding 4: Constitution amendment needed

Add to constitution (Section on Methodology):
```
Phase Boundaries

Each speckit phase has strict output boundaries:

/speckit.specify:
- Outputs: Problem statement, user stories, requirements, success criteria
- MUST NOT contain: Tool names, file paths, commands, configuration details
- Evidence: Describe by category/count, not by specific location

/speckit.plan:
- Outputs: Technical approach, tool selection, architecture decisions
- MAY contain: Tool names, high-level file structure
- MUST NOT contain: Exact implementation code

/speckit.tasks:
- Outputs: Specific implementation tasks
- MAY contain: File paths, commands, exact changes needed
```

## Corrective Actions Taken

1. ✅ Spec rewritten to remove all implementation details (Revision 2)
2. ✅ Checklist updated with revision history documenting the failure
3. ✅ This violation report created for template repo reference

## Recommended Template Repo Changes

1. [ ] Update spec-template.md with anti-pattern examples
2. [ ] Enhance checklist with explicit implementation detail examples
3. [ ] Add phase boundary section to constitution
4. [ ] Create automated validator for spec content
5. [ ] Add "Phase Boundary Violation" to known-issues/gotchas documentation

## Lessons Learned

1. **Investigation is not specification**: Understanding the problem requires looking at code; describing the problem does not require naming it
2. **Checklists need examples**: Abstract rules like "no implementation details" are interpreted liberally without concrete examples
3. **Human review caught this**: The 16-item automated checklist passed - only human review identified the violation
4. **Template methodology has blind spots too**: The irony of a blind-spot-audit having its own blind spot demonstrates the need for continuous methodology improvement
