# Implementation Plan: IAM Policy Remediation

## Technical Context

### Root Cause Analysis

**Critical Discovery**: The `IAMValidator` (`src/validators/iam.py`) does NOT support allowlist suppressions.

| Validator            | Allowlist Support                                          | Finding Types                   |
| -------------------- | ---------------------------------------------------------- | ------------------------------- |
| `LambdaIAMValidator` | Yes - calls `load_iam_allowlist()` and `should_suppress()` | LAMBDA-007, etc.                |
| `IAMValidator`       | **NO** - no allowlist integration                          | IAM-001, IAM-002, IAM-003, etc. |

This architectural gap means IAM-002 suppressions in `iam-allowlist.yaml` are ignored. The target repo's existing LAMBDA-007 suppression may also be failing due to context mismatch.

### Architecture Decision

**Options**:

| Option                                       | Description               | Risk   | Effort |
| -------------------------------------------- | ------------------------- | ------ | ------ |
| A. Add allowlist support to IAMValidator     | Template repo code change | Medium | High   |
| B. Add IAM-002 pattern to LambdaIAMValidator | Semantically incorrect    | Low    | Low    |
| C. Accept IAM-002 as expected finding        | No code changes           | Low    | None   |

**Selected**: **Option C** - Accept IAM-002 as expected finding (for now)

**Rationale**:

1. SC-004 states "No template repo code changes required"
2. IAM-002 finding is correctly flagging a `Resource: "*"` - the policy is technically permissive
3. The canonical source justification belongs in target repo documentation, not code suppression
4. Future feature (065+) can add allowlist support to IAMValidator if needed

### Constitution Compliance Check

| Principle                                | Compliance | Notes                                     |
| ---------------------------------------- | ---------- | ----------------------------------------- |
| Amendment 1.5 (Canonical Sources)        | **PASS**   | Canonical sources cited for both findings |
| Amendment 1.6 (No Quick Fixes)           | **PASS**   | Using speckit workflow, not ad-hoc        |
| Amendment 1.7 (Target Repo Independence) | **PASS**   | Target repo changes only                  |
| Amendment 1.8 (Managed Policies)         | N/A        | No new IAM resources                      |

## Implementation Strategy

### Phase 1: Debug LAMBDA-007 Suppression

The target repo's `iam-allowlist.yaml` has `lambda-cicd-deployment` entry with `passrole_scoped: true` context requirement.

**Hypothesis**: The `check_passrole_scoped()` function in `iam_allowlist.py` may be checking for `Resource: "*"` anywhere in the file, not just within the PassRole statement context.

**Investigation Steps**:

1. Run `/lambda-iam-validate` on target repo with verbose logging
2. Check if allowlist is loaded
3. Check if context evaluation passes
4. If context fails, identify the specific condition that fails

### Phase 2: Determine IAM-002 Resolution

**Current Behavior**: IAM-002 reports `Resource: "*"` in CloudFront cache policy statement.

**Options**:

1. Accept as informational (document in target repo README)
2. Add allowlist support to IAMValidator (template change - requires user confirmation)
3. Split CloudFront policy into Get and List statements (target repo change)

**Recommendation**: Option 1 (Accept as informational) for this feature. Option 2 can be a follow-up feature (065).

### Phase 3: Target Repo Documentation

Add justification comment to `preprod-deployer-policy.json` explaining why `Resource: "*"` is required for CloudFront List operations.

## Change Breakdown

### Target Repo Changes

| File                                                       | Change                                     | Justification                   |
| ---------------------------------------------------------- | ------------------------------------------ | ------------------------------- |
| `infrastructure/iam-policies/preprod-deployer-policy.json` | Add comment explaining CloudFront wildcard | Documentation per Amendment 1.5 |
| `infrastructure/iam-policies/prod-deployer-policy.json`    | Same comment if applicable                 | Consistency                     |
| `docs/iam-justifications.md`                               | Create justification doc                   | Canonical source citations      |

### Template Repo Changes

**None** - per SC-004. If investigation reveals template bug, will return to user for confirmation before proceeding.

## Validation Strategy

### Success Verification

1. **SC-001** (LAMBDA-007): Run `/validate` on target repo, verify LAMBDA-007 is SUPPRESSED
2. **SC-002** (IAM-002): Document as expected behavior (validator doesn't support suppression)
3. **SC-003** (Canonical sources): Verify `canonical_source` field on all allowlist entries
4. **SC-004** (No template changes): Git diff shows no changes in template repo src/

### Test Commands

```bash
# Verify template repo unchanged
git diff --stat src/

# Run validation on target repo
cd /home/traylorre/projects/sentiment-analyzer-gsk
/validate

# Check allowlist entries have canonical sources
grep -A2 "canonical_source" iam-allowlist.yaml
```

## Dependencies

- None - all changes target the target repo configuration

## Risks

| Risk                                                   | Mitigation                                                     |
| ------------------------------------------------------ | -------------------------------------------------------------- |
| LAMBDA-007 suppression still fails after investigation | Escalate to template repo bug fix (requires user confirmation) |
| IAM-002 creates noise in validation output             | Document as known informational finding                        |

## Estimated Scope

- Target repo: 2-3 files modified
- Template repo: 0 files modified
- Investigation: Debug LAMBDA-007 context evaluation
