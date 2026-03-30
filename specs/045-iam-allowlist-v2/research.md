# Research: IAM Allowlist V2

**Feature**: 045-iam-allowlist-v2
**Date**: 2025-12-05

## Research Questions

### Q1: How should IAM allowlist schema differ from secrets allowlist?

**Decision**: Use IAM-specific schema with finding_ids, context_required, and pattern matching

**Rationale**: The existing `iam-allowlist.yaml` in target repo already has a well-designed schema:

- `finding_ids`: Maps to specific validator rule IDs (LAMBDA-007, SQS-009, etc.)
- `context_required`: Enables conditional suppression (environment, passrole_scoped)
- `canonical_source`: Required for Amendment 1.5 compliance
- `classification`: runtime vs documentation (like secrets allowlist)

**Alternatives considered**:

- Reuse secrets allowlist schema → Rejected: IAM findings need different metadata (finding_ids vs regex patterns)
- Single unified allowlist → Rejected: Too complex, different concerns

### Q2: Where should allowlist be loaded from?

**Decision**: Load from repo root `iam-allowlist.yaml` with fallback to no suppression

**Rationale**:

- Consistent with secrets methodology (`allowlist.yaml` at repo root)
- Target repos may not have allowlist - graceful degradation
- Template repo doesn't need allowlist (validates others)

**Alternatives considered**:

- `.specify/` subdirectory → Rejected: Not all repos use speckit structure
- Environment variable path → Rejected: Adds deployment complexity

### Q3: How to implement context-aware matching?

**Decision**: Evaluate context_required conditions against file path and policy structure

**Rationale**: The iam-allowlist.yaml already defines context conditions:

```yaml
context_required:
  environment: preprod # Match via file path pattern
  passrole_scoped: true # Match via PassRole Resource constraint
```

Context derivation:

- `environment`: Extract from file path (dev-_, preprod-_, prod-\*)
- `passrole_scoped`: Parse policy to check PassRole has Resource constraints

**Alternatives considered**:

- Explicit context parameter → Rejected: Requires validator API changes
- File-based context files → Rejected: Adds maintenance burden

### Q4: How to handle multiple matching allowlist entries (per clarification)?

**Decision**: Most specific match wins - entry with most context_required conditions

**Rationale**: Clarified in spec session 2025-12-05. Implementation:

1. Find all matching entries by finding_id
2. Count context_required conditions for each
3. Select entry with highest count
4. If tie, use first match

### Q5: Should SUPPRESSED be a new status or reuse existing?

**Decision**: Check if SUPPRESSED exists in models.py, add if not

**Rationale**: Looking at existing Status enum in models.py - need to verify current values. SUPPRESSED should be distinct from PASS (intentionally allowed) and FAIL (genuine issue).

## Key Design Decisions

| Decision               | Choice                                        | Rationale                       |
| ---------------------- | --------------------------------------------- | ------------------------------- |
| Allowlist schema       | IAM-specific with finding_ids                 | Already exists in target repo   |
| Load location          | Repo root iam-allowlist.yaml                  | Consistent with secrets pattern |
| Context derivation     | Path-based environment, policy-based passrole | No API changes needed           |
| Multi-match resolution | Most restrictive wins                         | Per spec clarification          |
| Missing allowlist      | No suppression (graceful)                     | Backward compatible             |

## Implementation Approach

1. **iam_allowlist.py module**:

   - `load_iam_allowlist(repo_path)` → `IAMAllowlist | None`
   - `IAMAllowlist.should_suppress(finding_id, file_path, policy_content)` → `bool`
   - `IAMAllowlist.get_suppression_reason(finding_id)` → `str`

2. **Validator integration**:

   - Load allowlist once at validator init
   - Check `should_suppress()` before adding finding
   - If suppressed, add with status=SUPPRESSED instead of FAIL

3. **Target repo updates**:
   - Extend SQS-009 allowlist entry to cover dev environment
   - No structural changes needed - schema already correct

## Canonical Sources

- AWS CI/CD Best Practices: https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-cicd-litmus/cicd-best-practices.html
- OWASP CI/CD Security: https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html
- AWS Lambda Access Control: https://docs.aws.amazon.com/lambda/latest/dg/access-control-resource-based.html
- Rhino Security Privilege Escalation: https://rhinosecuritylabs.com/aws/aws-privilege-escalation-methods-mitigation/
