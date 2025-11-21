# Preprod Deployment - Pre-Push Analysis

**Date**: 2025-11-20
**Status**: CRITICAL REVIEW - DO NOT PUSH UNTIL RESOLVED
**Reviewer**: Pre-deployment checklist for production readiness

---

## ⚠️ CRITICAL ISSUES IDENTIFIED

### 1. Promotion Workflow (dev→preprod→prod)

**CURRENT STATE**: ❌ BROKEN
- No automated promotion path configured
- Manual terraform apply required for each environment
- No connection between dev merge → preprod deploy

**REQUIRED STATE**: ✅ AUTOMATED
```
Merge to main → Dev tests pass → Auto-deploy to preprod →
  Preprod tests pass → GATE: Manual approval → Deploy to prod
```

**BLOCKING ISSUES**:
- [ ] No workflow to trigger preprod deploy after dev tests pass
- [ ] No workflow to trigger prod deploy after preprod validation
- [ ] No artifact promotion (Lambda packages built once, promoted through envs)
- [ ] Terraform apply happens independently per environment

**SOLUTION NEEDED**:
Create promotion workflows:
- `.github/workflows/promote-to-preprod.yml` (auto-trigger after dev tests)
- `.github/workflows/promote-to-prod.yml` (manual approval after preprod validation)

---

### 2. Gatekeeping Controls

**CURRENT STATE**: ❌ UNDEFINED
- No clear approval gates
- No policy on who can approve prod deployment
- Dependabot auto-merge conflicts with manual gates

**REQUIRED STATE**: ✅ DEFINED

**Security Updates** (Dependabot):
```
Dependabot PR → Dev tests → Auto-merge → Auto-deploy preprod →
  Preprod tests → Auto-deploy prod (NO HUMAN GATE)
```

**Feature Changes** (Human):
```
Human PR → Dev tests → Manual merge → Auto-deploy preprod →
  Preprod tests → GATE: Manual approval → Deploy prod
```

**CRITICAL QUESTION**: How to distinguish Dependabot from human changes?

**SOLUTION**:
- Use GitHub branch protection + auto-merge for Dependabot
- Use GitHub environments with required reviewers for human PRs
- Separate workflows based on PR author

**BLOCKING ISSUES**:
- [ ] No GitHub environment configured (preprod, prod)
- [ ] No required reviewers set
- [ ] No distinction between security vs feature PRs
- [ ] Current preprod workflow requires manual trigger (won't auto-deploy)

---

### 3. Preprod Alarms and Monitoring

**CURRENT STATE**: ❌ MISSING
- Preprod has same Terraform as dev (which has no real resources)
- No CloudWatch alarms configured for preprod
- No alerting on preprod test failures

**REQUIRED STATE**: ✅ PRODUCTION-LIKE

**Preprod Must Have**:
- Lambda error alarms (>5 errors in 5 min)
- DynamoDB throttling alarms (capacity issues)
- SNS delivery failures
- Integration test failure notifications
- Cost anomaly detection (detect runaway resources)

**BLOCKING ISSUES**:
- [ ] Terraform modules assume prod has alarms, preprod doesn't
- [ ] No SNS topic for preprod alerts
- [ ] No email/Slack integration for preprod failures
- [ ] Integration test failures are silent (only visible in GitHub Actions)

**SOLUTION NEEDED**:
- Add CloudWatch alarms to all Terraform modules
- Create preprod-alerts SNS topic
- Configure GitHub Actions to send failure notifications
- Add cost budget alerts for preprod

---

### 4. Preprod Tests (Canary Included)

**CURRENT STATE**: ⚠️ INCOMPLETE
- Integration tests exist (`test_*_preprod.py`)
- No canary test to validate health endpoint
- If canary breaks in prod, we find out when customers complain

**REQUIRED STATE**: ✅ CANARY VALIDATED

**Preprod Must Test**:
1. **Canary health check** (same as prod will use)
2. **End-to-end data flow** (ingestion → analysis → dashboard)
3. **Error scenarios** (invalid data, timeouts, retries)

**BLOCKING ISSUES**:
- [ ] No canary test in preprod suite
- [ ] Canary itself not tested before prod (meta-problem!)
- [ ] No load testing (what if preprod passes but prod fails under load?)

**SOLUTION**:
```python
# tests/integration/test_canary_preprod.py
def test_canary_health_check():
    """
    Test the ACTUAL canary that will run in prod.

    This ensures the canary itself works before we deploy to prod.
    If this fails, the canary is broken and prod will have no monitoring.
    """
    # Call the same health endpoint prod canary will call
    # Verify response structure matches what prod expects
```

---

### 5. NewsAPI Mock Messages

**CURRENT STATE**: ⚠️ MINIMAL
- Only 1 happy path message in tests
- Real NewsAPI returns various edge cases we don't test

**REAL NEWSAPI SCENARIOS**:
```json
// Happy path
{"articles": [{"title": "...", "url": "...", ...}]}

// Empty response
{"articles": []}

// Missing fields
{"articles": [{"title": "...", "url": null}]}

// Large response (100 articles)
{"articles": [{...}, {...}, ...]}  // 100 items

// API error
{"status": "error", "code": "rateLimited", "message": "..."}

// Partial data
{"articles": [{"title": "...", "description": null, ...}]}
```

**BLOCKING ISSUES**:
- [ ] Only 1 test message (happy path)
- [ ] No edge case coverage (missing fields, empty, errors)
- [ ] No bulk testing (100 articles at once)
- [ ] No API error handling validation

**SOLUTION NEEDED**:
Create comprehensive NewsAPI fixture library:
- `fixtures/newsapi_responses.py` with all scenarios
- Update E2E tests to cover each scenario
- Separate test per edge case

---

### 6. Credentials Strategy (CRITICAL SECURITY)

**CURRENT STATE**: ❌ DANGEROUS
- Likely using same NewsAPI key for dev/preprod/prod
- Likely using same AWS access keys for all environments
- No credential rotation strategy
- Secrets are in GitHub (single point of compromise)

**SECURITY IMPLICATIONS**:
- ⚠️ Preprod failure could leak prod credentials
- ⚠️ Compromised dev key = compromised prod
- ⚠️ No way to revoke preprod without breaking prod

**REQUIRED STATE**: ✅ ISOLATED

**Credential Separation**:
```
Environment    NewsAPI Key          AWS Secrets              DynamoDB
-----------    -----------          -----------              --------
dev            N/A (mocked)         N/A (mocked)             Mocked
preprod        preprod-newsapi-key  preprod-secrets-arn      preprod-sentiment-items
prod           prod-newsapi-key     prod-secrets-arn         prod-sentiment-items
```

**BLOCKING ISSUES**:
- [ ] No separate NewsAPI key for preprod
- [ ] Secrets Manager ARN likely points to same secret
- [ ] GitHub secrets may be shared across environments
- [ ] No IAM policy limiting preprod to preprod resources only

**SOLUTION** (My Strong Recommendation):

**YES, absolutely create separate credentials for preprod**:

1. **NewsAPI Keys**:
   - Preprod: Free tier key (sufficient for testing)
   - Prod: Paid tier key (higher rate limits)
   - Benefit: Preprod can't exhaust prod API quota

2. **AWS Credentials**:
   - Preprod: IAM role with `*-preprod-*` resource access only
   - Prod: IAM role with `*-prod-*` resource access only
   - Benefit: Preprod can't accidentally modify prod resources

3. **Secrets Manager**:
   - `arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:preprod-newsapi-key`
   - `arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:prod-newsapi-key`
   - Benefit: Rotation doesn't affect other environments

4. **GitHub Secrets**:
   - `PREPROD_AWS_ACCESS_KEY_ID` / `PREPROD_AWS_SECRET_ACCESS_KEY`
   - `PROD_AWS_ACCESS_KEY_ID` / `PROD_AWS_SECRET_ACCESS_KEY`
   - Use GitHub Environments to scope secrets

**COST**: $0 (AWS Secrets Manager charges per secret, but we already have 1)

---

### 7. AWS Resource Mirroring

**CURRENT STATE**: ❌ INCOMPLETE
- Terraform modules exist but may not create all resources
- No clarity on which resources are environment-specific

**REQUIRED RESOURCES** (Preprod Must Match Prod):

| Resource | Dev | Preprod | Prod | Notes |
|----------|-----|---------|------|-------|
| DynamoDB Table | ❌ Mock | ✅ Real | ✅ Real | Same schema, different name |
| SNS Topic | ❌ Mock | ✅ Real | ✅ Real | Analysis notifications |
| SQS Queue | ❌ Mock | ✅ Real | ✅ Real | DLQ for analysis |
| Lambda (Ingestion) | ❌ Mock | ✅ Real | ✅ Real | Same code, different env vars |
| Lambda (Analysis) | ❌ Mock | ✅ Real | ✅ Real | Mock ML in preprod |
| Lambda (Dashboard) | ❌ Mock | ✅ Real | ✅ Real | |
| Secrets Manager | ❌ Mock | ✅ Real | ✅ Real | Separate secrets per env |
| S3 Bucket | ❌ Mock | ✅ Real | ✅ Real | Lambda packages |
| EventBridge Rule | ❌ Mock | ✅ Real | ✅ Real | 2hr in preprod vs 15min in prod |
| CloudWatch Alarms | ❌ N/A | ✅ Real | ✅ Real | Same thresholds |
| IAM Roles | ❌ N/A | ✅ Real | ✅ Real | Environment-scoped |

**ML COMPONENT** (Special Case):
- Dev: ❌ Mocked (unittest.mock)
- Preprod: ❌ Mocked (too expensive)
- Prod: ✅ Real (transformers pipeline)

**BLOCKING ISSUES**:
- [ ] Current Terraform may not create preprod Lambda functions
- [ ] No S3 bucket for preprod Lambda packages
- [ ] EventBridge schedule may not be environment-aware
- [ ] IAM roles may not have environment prefix

**SOLUTION NEEDED**:
- Verify Terraform creates ALL resources with `var.environment` prefix
- Add preprod-specific tfvars with conservative settings
- Create TODO to consider preprod ML (later optimization)

---

### 8. Pipeline Failure Recovery

**CURRENT STATE**: ❌ UNDEFINED
- No documented recovery strategy
- Pipeline likely blocks on failure
- No automatic rollback

**FAILURE SCENARIOS**:

**Scenario 1**: Dev tests fail
```
PR → Dev tests FAIL → BLOCK: PR can't merge
Recovery: Fix code, push again (automatic)
```

**Scenario 2**: Preprod deployment fails (Terraform)
```
Merge → Preprod deploy FAIL → BLOCK: Preprod broken, can't validate
Recovery: Manual terraform fix, re-run workflow
```

**Scenario 3**: Preprod tests fail
```
Merge → Preprod deploy OK → Preprod tests FAIL → BLOCK: Can't promote to prod
Recovery: Rollback preprod, fix in dev, re-merge
```

**Scenario 4**: Prod deployment fails
```
Manual approval → Prod deploy FAIL → CRITICAL: Prod may be partially deployed
Recovery: ??? (undefined)
```

**DEPENDABOT REQUIREMENT**:
```
Dependabot PR → Dev tests PASS → Auto-merge → Preprod deploy PASS →
  Preprod tests PASS → Auto-deploy prod

IF ANY STEP FAILS:
  → Dependabot PR stays open
  → Human investigates
  → Fix issue
  → Dependabot rebases and retries
```

**BLOCKING ISSUES**:
- [ ] No rollback strategy for failed preprod deploy
- [ ] No rollback strategy for failed prod deploy
- [ ] Dependabot can't auto-deploy prod (requires manual approval)
- [ ] No way to distinguish "safe" Dependabot PRs from "risky" ones

**SOLUTION NEEDED**:

**Option 1**: Full Automation (High Risk)
- Dependabot → Dev → Preprod → Prod (all automatic)
- Pro: Fast security updates
- Con: Bad dependency could break prod automatically

**Option 2**: Tiered Automation (Recommended)
- **Security patches** (Dependabot with `security` label): Auto all the way
- **Minor/patch updates**: Auto to preprod, manual approval for prod
- **Major updates**: Manual review at every stage

Implement with GitHub Actions conditional workflows based on Dependabot PR metadata.

---

## RISK ASSESSMENT

| Issue | Severity | Blocks Push? | Can Fix Later? |
|-------|----------|--------------|----------------|
| 1. Promotion workflow | CRITICAL | ❌ YES | ❌ NO - Core architecture |
| 2. Gatekeeping | CRITICAL | ❌ YES | ❌ NO - Security requirement |
| 3. Alarms | HIGH | ⚠️  MAYBE | ✅ YES - Can add post-deploy |
| 4. Canary test | HIGH | ⚠️  MAYBE | ✅ YES - Nice to have |
| 5. NewsAPI mocks | MEDIUM | ✅ NO | ✅ YES - Coverage improvement |
| 6. Credentials | CRITICAL | ❌ YES | ❌ NO - Security fundamental |
| 7. Resource mirror | CRITICAL | ❌ YES | ❌ NO - Preprod won't work |
| 8. Failure recovery | HIGH | ⚠️  MAYBE | ⚠️  PARTIAL - Document first |

---

## RECOMMENDATION

**DO NOT PUSH YET**

We have **4 CRITICAL blockers** that will cause preprod to fail or create security vulnerabilities:

1. ❌ **Promotion workflow doesn't exist** → Preprod never deploys
2. ❌ **Gatekeeping undefined** → Dependabot can't auto-promote
3. ❌ **Credentials not separated** → Security vulnerability
4. ❌ **Resources not verified** → Preprod may be incomplete

---

## PROPOSED FIX STRATEGY

### Phase 1: Make Preprod Work (Blockers 1, 4, 6)
1. Create automated promotion workflow
2. Verify Terraform creates all preprod resources
3. Create separate preprod credentials
4. Test preprod deploy manually
5. Verify integration tests pass

### Phase 2: Add Safety (Blocker 2, 8)
6. Configure GitHub Environments (preprod, prod)
7. Add required reviewers for prod
8. Create Dependabot auto-promotion workflow
9. Document failure recovery procedures

### Phase 3: Improve Coverage (Issues 3, 5)
10. Add CloudWatch alarms to preprod
11. Create canary test
12. Expand NewsAPI mock scenarios

**Estimated Time**: 4-6 hours for Phase 1 (blocking), 2-3 hours for Phase 2

---

## INTERVIEW PERSPECTIVE

**What Your Interviewer is Looking For**:

✅ **You identified the issues** (fantastic start!)
✅ **Systematic analysis** (this document)
✅ **Risk assessment** (blocking vs non-blocking)
✅ **Prioritization** (what to fix first)
✅ **Security awareness** (credential separation)
✅ **Production mindset** (failure recovery)

**Red Flags to Avoid**:
❌ Pushing broken code ("we'll fix it later")
❌ Mixing credentials across environments
❌ No rollback strategy
❌ Dependabot can break prod automatically

**Ideal Narrative**:
> "I built the three-environment architecture, then did a critical pre-deployment
> review. I identified 4 blocking issues that would prevent preprod from working
> and 1 critical security issue with credential separation. I'm fixing these
> systematically before pushing to production-facing infrastructure."

---

## NEXT STEPS

**Shall we**:
1. Fix the 4 CRITICAL blockers before pushing? (Recommended)
2. Push current state and create issues to track fixes? (Risky)
3. Pause and design the full promotion workflow first? (Safest)

**Your call - your life depends on this!**
