# Stage 3: Adversarial Spec Review — 1279-playwright-verify

## Review Checklist

### Completeness
- [x] Problem clearly stated with evidence (3 PRs with CANCELLED Playwright jobs)
- [x] Root cause identified (auto-merge kills non-required checks)
- [x] Solution scoped narrowly (pin + observe, no code fixes)
- [x] Acceptance criteria are testable and objective
- [x] Dependencies listed and status verified

### Contradictions
- **None found.** The spec correctly separates "apply the pin" from "observe the results."

### Ambiguities
- **Q: What if Playwright still fails after the pin fix?** Resolution: The spec explicitly says
  this is an observability feature. Failure is a valid outcome -- we document it.
- **Q: What if CI takes >1 hour?** Resolution: Playwright job has `timeout-minutes: 5`. The
  entire workflow should complete in <15 minutes.
- **Q: What if auto-merge gets enabled accidentally?** Resolution: We use `gh pr create` without
  `--auto` flag. The PR Merge workflow's auto-merge job requires specific conditions.

### Attack Surface (Security Review)
- No new attack surface. Adding a version pin to a dev-only requirements file.
- No secrets, credentials, or infrastructure changes.
- No new dependencies introduced.

### Edge Cases
1. **Pydantic pin already applied by another PR**: Check before applying. Currently confirmed
   NOT present in `requirements-dev.txt`.
2. **Merge conflict with concurrent PRs**: Unlikely. The change is 2 lines appended to end of file.
3. **Playwright job cancelled again despite no auto-merge**: Only possible if someone manually
   cancels or GitHub has an outage. Monitor the run.

### Verdict
**PASS** -- Spec is complete, unambiguous, and narrowly scoped. Proceed to planning.
