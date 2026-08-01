# Cross-reference map: `.specify/memory/constitution.md`

Evidence for criterion 9. Rebuilt 31 July 2026 after adversarial refutation overturned the
previous version's central claim.

Couplings were measured against the document at 641 lines / 6000 words. Line citations are updated
to the post-amendment file, 635 lines / 5953 words, after the black and bandit clauses came out on
31 July 2026. No coupling finding changed; the amendment touched only tool names.

The previous version reported **zero cross-section references** and concluded a by-section split
was safe. That conclusion is withdrawn. It rested on a single detector, and the null result was a
fact about the detector rather than about the document.

## Contents

- [Method](#method)
- [Section map](#section-map)
- [Cross-references, by strategy](#cross-references-by-strategy)
- [Cross-cutting terms, full vocabulary](#cross-cutting-terms-full-vocabulary)
- [Contradictions and dangling references](#contradictions-and-dangling-references)
- [Conformance findings against the live repo](#conformance-findings-against-the-live-repo)
- [Seam verdict](#seam-verdict)
- [Prerequisites for any split](#prerequisites-for-any-split)
- [Criterion 3 is not judgeable as written](#criterion-3-is-not-judgeable-as-written)
- [Corrections to the previous version](#corrections-to-the-previous-version)

## Method

Eight detection strategies. Strategy 8 is the one the previous version used alone.

| # | Strategy | What it detects | Cross-section hits |
|---|---|---|---|
| 1 | Heading-title mentions | Prose naming another section by its exact heading string | 13 |
| 2 | Identifier tokens | An identifier defined in one section, used in another | 4 identifiers |
| 3 | Acceptance-criteria mapping | AC bullets tested against requirements stated elsewhere | 13 bullets |
| 4 | 4-gram restatement | Normative content restated in a second section | 2 |
| 5 | Anaphoric obligation pointers | "at the bottom", "see list above" | 1 |
| 6 | Process-ordering dependencies | "before pushing", "before integration tests run" | 5 |
| 7 | Definite-article anaphora | "the retention policy", "the metrics backend" | 3 |
| 8 | Explicit-phrase regex | "see section", "refer to", "as described above" | **0** |

Strategies 1, 2, 4, 6 and 7 are scripted (`spans.py`, `refs.py`, `ngram.py`, retained in the job
scratch directory). Strategy 3 requires reading each bullet and locating the requirement it tests;
grep cannot do it. Strategy 5 is a small hand-built pattern list.

Two methodological choices, stated because they change counts:

- **Fenced code blocks are counted.** `dashboard_api` inside the Python example at L225 is a hit
  for `dashboard`. Excluding code blocks lowers the raw counts but hides the two checklists at
  L411 and L619, which are both code blocks and are the sharpest contradiction in the document.
- **Stem families are counted separately from exact tokens.** A rule stated as "approved" in one
  section and "approval" in another still couples them. Exact-token counting gives `approv*` 4
  sections; stem counting gives 8. Both are reported.

## Section map

Reused from the previous version. Independently verified, zero delta across all 23 rows, ranges
contiguous, word counts summing to 5953 = `wc -w`. Re-verified here by assertion in `spans.py`.

| Lines | Words | Style | Section |
|---|---|---|---|
| 1-2 | 5 | atx | Sentiment Analyzer, Constitution |
| 3-6 | 24 | setext | Purpose |
| 7-10 | 30 | setext | Scope |
| 11-12 | 5 | setext | Minimal Requirements (Bare Minimum) |
| 13-20 | 121 | numbered | 1) Functional Requirements |
| 21-25 | 41 | numbered | 2) Non-Functional Requirements |
| 26-45 | 340 | numbered | 3) Security & Access Control |
| 46-51 | 95 | numbered | 4) Data & Model Requirements |
| 52-56 | 39 | numbered | 5) Deployment Requirements **(duplicate number, p0-004)** |
| 57-95 | 758 | numbered | 5) Deployment Requirements (Serverless / Event-driven preferred) |
| 96-103 | 184 | **bare** | Architecture & Tech Stack Notes **(invisible heading)** |
| 104-112 | 138 | **bare** | Acceptance Criteria (serverless stack) **(invisible heading)** |
| 113-178 | 905 | numbered | 6) Observability & Monitoring |
| 179-371 | 1371 | numbered | 7) Testing & Validation |
| 372-386 | 132 | setext | Interfaces (Minimal Contract) |
| 387-395 | 98 | setext | Acceptance Criteria (Minimal) |
| 396-400 | 34 | setext | Operational Notes |
| 401-474 | 428 | numbered | 8) Git Workflow & CI/CD Rules |
| 475-504 | 372 | setext | Design & Diagrams (Canva preferred) |
| 505-520 | 96 | setext | Sensitive Security Documentation |
| 521-573 | 308 | numbered | 9) Tech Debt Tracking |
| 574-589 | 203 | setext | Amendments & Governance |
| 590-635 | 226 | numbered | 10) Local SAST Requirement |

## Cross-references, by strategy

### Strategy 1: heading-title mentions (13)

The amendment log at L578-588 names other sections by their exact heading strings. Five entries
use the word "section" literally (L580, 582, 584, 586, 588).

| Line | Names | Target section |
|---|---|---|
| 578 | Environment & Stage Testing Matrix; External Dependency Mocking; Synthetic Test Data; Implementation Accompaniment Rule | 7-Testing |
| 578 | Git Workflow & CI/CD Rules; Pre-Push Requirements; Pipeline Monitoring; Branch Lifecycle | 8-Git |
| 580 | Pipeline Check Bypass | 8-Git |
| 582 | Sensitive Security Documentation | SensitiveSecDocs |
| 584 | Tech Debt Tracking | 9-TechDebt |
| 586 | Deterministic Time Handling | 7-Testing |
| 588 | Local SAST Requirement | 10-LocalSAST |

13 exact heading-string pointers across 5 target sections. A 14th, "bypass prohibition" at L578,
is a paraphrase of the L446 heading rather than an exact match, so it is excluded from the count.

**Name collision, a separate hazard.** `Acceptance Criteria` is used as a heading in 8 places:
L104, L144, L171, L364, L387, L500, L567, L628. Under a by-section split an agent asked to load
"Acceptance Criteria" has eight candidates. This is ambiguity rather than a pointer, and it is
counted separately.

`Pre-push checklist` collides the same way: L411 and L619, and the L619 instance is titled
"(updated)", which asserts supersession over the other without deleting it.

### Strategy 2: identifier tokens (4)

| Identifier | Defined | Used | Distance |
|---|---|---|---|
| `/v1/sources` | L374 [Interfaces] | L153 [6-Observability] | 221 lines |
| `model_version` | L47 [4-DataModel] | 7 sections, 11 hits | up to 351 lines |
| `docs/TECH_DEBT_REGISTRY.md` | L527 [9-TechDebt] | L584 [Amendments] | 57 lines |
| `ConditionExpression` | L81 [5-Serverless] | L99 [ArchNotes] | 18 lines |

`model_version` spans 4-DataModel, 5-Serverless, ArchNotes, 6-Observability, Interfaces,
AC-Minimal, OpNotes.

### Strategy 3: acceptance criteria to requirement (13 bullets, 100% outbound)

Neither Acceptance Criteria block states a requirement. Every bullet tests one stated elsewhere,
so neither block can be read, split, or moved independently of its targets.

**AC-serverless (L104-112), 7 of 7 bullets outbound:**

| Bullet | Tests |
|---|---|
| L105 Terraform deploys via the documented CI/CD pipeline | L59-72 [5-Serverless] |
| L106 CI verifies fmt/validate/plan, reviewed plan for prod | L68, L65 [5-Serverless] |
| L107 SNS/SQS with DLQs, visibility timeout, access policies | L75-78 [5-Serverless] |
| L108 Lambda consumers idempotent, dedup and replay tested | L76 [5-Serverless], L100 [ArchNotes] |
| L109 DynamoDB key design, PITR, encryption, conditional write | L80-83 [5-Serverless] |
| L110 CloudWatch/X-Ray end to end, dashboard maps to telemetry | L91 [5-Serverless] |
| L111 IAM least-privilege, secrets in Secrets Manager, SAST in CI | L98 [ArchNotes], L88 [5-Serverless] |

**AC-Minimal (L387-395), 6 of 6 bullets outbound:**

| Bullet | Tests |
|---|---|
| L389 ingests RSS and Twitter sources, output schema | L14-15 [1-Functional], L47 [4-DataModel] |
| L390 deduplication prevents re-processing | L17 [1-Functional] |
| L391 rate-limits and backoff, simulated in integration test | L29 [3-Security] |
| L392 e2e passes with pinned model_version and fixture | L49-50 [4-DataModel] |
| L393 pause/resume works, recovery after transient failures | L19 [1-Functional] |
| L394 secrets absent from source control, TLS, admin auth | L27, L30, L31 [3-Security] |

### Strategy 4: 4-gram restatement (2)

| Shared text | Locations | Status |
|---|---|---|
| `sentiment positive neutral negative score` | L47 [4-DataModel], L380 [Interfaces] | **divergent, see below** |
| `re processing same published item` | L17 [1-Functional], L390 [AC-Minimal] | consistent restatement |

### Strategy 5: anaphoric obligation pointers (1)

L576 "Maintain a Version and Last Amended date **at the bottom**" points at L635, 65 lines away,
across a section boundary. The previous version proposed deleting L635 while asserting that no
deletion could break a pointer, and quoted L576 in its own text.

L146 "(see list above)" points at L141, inside the same section. Correctly dismissed, upheld.

### Strategy 6: process-ordering dependencies (5)

**Four sections independently legislate the pre-push gate.** No section references any other.

| Section | Rule | Line |
|---|---|---|
| 7-Testing | Never push code that fails local unit tests; run the full suite before pushing | L246, L251 |
| 8-Git | Pre-Push Requirements a-d, plus a checklist code block | L405-416 |
| 9-TechDebt | Registry entries before PR merge | L570 |
| 10-LocalSAST | Bandit pre-commit, `make sast` before push, checklist "(updated)" | L592, L596, L619-625 |

The fifth: L310 [7-Testing] "Terraform MUST have dev workspace deployed before integration tests
run" depends on the IaC requirements at L59-72 [5-Serverless].

### Strategy 7: definite-article anaphora (3)

- **Bidirectional 5-Serverless ↔ 6-Observability.** L91 refers to "the dashboard" (defined at
  L120); L140 refers to "the metrics backend" (defined at L91). Each section's text presumes the
  other's definition.
- **L399 "the retention policy" is dangling.** The only other use of "retention" in the document
  is L101, SQS message retention, a different thing. The policy is never defined.
- **L48 and L131 both defer to an undefined "documented policy"** for raw-text storage. L48 says
  "the storage policy must be documented"; L131 says snippets "must be stored/encrypted under a
  documented policy". Two sections, two references, no definition, and it is not stated whether
  they mean the same policy.

## Cross-cutting terms, full vocabulary

The previous version checked 11 hand-picked terms and presented the result as a measurement. This
sweeps every token and every 2-3 gram in the document, then reports the ranking. Exact-token
counts unless marked.

| Term | Sections | Hits |
|---|---|---|
| `test` | 11 | 43 |
| `source` | 11 | 31 |
| `security` | 11 | 24 |
| `required` | 11 | 15 |
| `requirements` | 11 | 14 |
| `secret*` (stem) | **9** | 18 |
| `api` | 9 | 24 |
| `service` | 9 | 16 |
| `acceptance criteria` (bigram) | 8 | 10 |
| `approv*` (stem) | **8** | 15 |
| `code` | 8 | 28 |
| `external` | 8 | 26 |
| `ci` | 7 | 17 |
| `model_version` | 7 | 11 |
| `secrets` (exact) | 7 | 14 |
| `iam` | 6 | 8 |
| `dashboard` | 5 | 23 exact, 25 with `dashboards` and `dashboard_api` |
| `sast` | 5 | 15 |
| `terraform` | 4 | 12 |

The previous version's two "genuinely cross-cutting" terms, `model_version` (7) and SAST (5), rank
14th and 18th. Eight terms tie or beat SAST's span; five beat `model_version`'s.

`sast` at 5 sections is confirmed, but only after fixing a tokenizer defect. Splitting on
non-word characters is required, because `SAST/IaC` and `SAST/secret scanning` otherwise collapse
into single tokens and undercount the span by two sections. The first pass of this rebuild had that
defect and reported `sast` at 3.

## Contradictions and dangling references

Two rules that can only both be followed by choosing one are a criterion 4 defect.

### C1. Two pre-push checklists, neither referencing the other

```
L411-417  [8-Git]                    L619-625  [10-LocalSAST, titled "(updated)"]
  ruff check src/ tests/               make validate      # fmt + lint + security + sast
  ruff format src/ tests/              make test-local    # unit + integration
  git commit -S -m "message"           git commit -S
  git push origin feature-branch       git push
```

8-Git runs no SAST and no tests. 10-LocalSAST makes no explicit lint or format call and drops the
`origin feature-branch` argument that L409(d) requires. An agent loading either section alone gets
a pre-push gate that is wrong in a different direction. This is the seam test failing in its exact
stated form: summarising one side loses information the other side needs.

### C2. Two output schemas for the same object

| Field | L47 [4-DataModel] | L380 [Interfaces] |
|---|---|---|
| `text_snippet` | `?: string` | absent |
| `received_at` | absent | `ISO8601` |
| `url` | required | `url?` optional |
| `score` | `float(0-1)` | `number`, no range |

### C3. Section 10's required patterns are unreadable alone

L605-609 lists five CWE patterns local SAST must detect. Their normative definitions are in
section 3: log injection at L39, hardcoded secrets at L31, SQL injection at L33-43. A bundle
containing only section 10 states obligations whose meaning lives 566 lines away.

### C4. Dangling policy references

L399 "the retention policy", and the L48 / L131 "documented policy" pair. Three references, zero
definitions.

## Conformance findings against the live repo

Recorded because the brief names documented-versus-actual divergence as the catalogued smell that
motivates the conformance checks. All verified against the working tree, not against CLAUDE.md.

- **The "(updated)" checklist is the one that conforms.** `make validate` (Makefile:42) and
  `make test-local` (Makefile:104) both exist. This settles C1 on evidence: keep the L619 version,
  delete the L411 one.
- **`make validate` is a partially inert gate.** `security:` runs `pip-audit ... || true`
  (Makefile:73) and `sast:` runs `bandit ... || true` (Makefile:78), so neither can fail the
  build. `semgrep scan --config auto --error` (Makefile:81) carries no `|| true` and can. So the
  L632 criterion "No new code merged with HIGH/MEDIUM SAST findings" is enforced for Semgrep only.
  This corrects the refutation record, which stated `make validate` cannot fail on a security
  finding; it can, through Semgrep alone.

### Black and Bandit: the document now leads the configuration

The constitution was amended on 31 July 2026 to remove both tools. It no longer names either one.
Per the brief's direction, the document is normative and the configuration is now the thing that
disagrees, so every site below is a conformance gap to close rather than a doc-staleness bug.

**Black.** One real install and one dependency-bot entry. Everything else is already a comment
recording its removal.

| Site | State |
|---|---|
| `requirements-dev.txt:35` | `black==26.5.1`, installed |
| `requirements-ci.txt:56` | `black==26.5.1`, installed |
| `.github/dependabot.yml:70` | grouped for updates |
| `pyproject.toml:66`, `.pre-commit-config.yaml:56`, `Makefile:60`, `pr-checks.yml:58` | comments recording removal |
| `CONTRIBUTING.md:247` | commented-out invocation |

The repo already disagreed with itself before the amendment: black was installed while four
tool paths recorded it as removed and wired only Ruff.

**Bandit.** Seven live sites, matching the standing count.

| Site | State |
|---|---|
| `.pre-commit-config.yaml:99-104` | hook, runs every commit |
| `Makefile:76-78` | `sast` target, `\|\| true` |
| `Makefile:89-90` | `audit-pragma` target, `--ignore-nosec` |
| `pyproject.toml:210-214` | `[tool.bandit]` config |
| `pyproject.toml:54` | `bandit==1.9.4` dev dep |
| `requirements-dev.txt:38` | `bandit==1.9.4` |
| `requirements-ci.txt:59` | `bandit==1.9.4`, installed in CI, invoked by no step |

Two dependencies to resolve when the repo work is scheduled, recorded here so they are not
discovered late:

- **6 `# nosec` pragmas** in `src/` (`analysis/sentiment.py:60,102,121`,
  `shared/adapters/tiingo.py:48`, `dashboard/sentiment.py:72`, `shared/adapters/finnhub.py:51`)
  lose their reader. `Makefile:89-90` is the audit that reads them.
- **`pyproject.toml:91`** `external = ["B108", "B202", "B324"]` exists to stop RUF100 flagging
  those Bandit codes. It becomes dead once no `# nosec B###` comment remains.

## Seam verdict

**A by-section split is not safe as-is.** This reverses the previous version.

Counting sections involved in at least one non-trivial coupling: 15 of 23. The 8 remaining are
Title, Purpose, Scope, Minimal Requirements, 2-NonFunctional, 5-Deploy-dup, Design, and
SensitiveSecDocs. Of those, 5-Deploy-dup is already slated for deletion under p0-004 and
SensitiveSecDocs is an inbound target of the amendment log.

Genuinely free-standing on content: Title, Purpose, Scope, Minimal Requirements, 2-NonFunctional,
Design. Together 477 words, **roughly 8% of the document**.

Design earns its place on that list on content but not on naming. Its Acceptance Criteria block at
L500-503 tests only its own requirements (`diagrams/README.md` at L482, the SVG and PNG exports at
L481, provenance metadata at L494), so it is genuinely intra-section, unlike the two AC blocks
above. It still participates in the 8-way `Acceptance Criteria` heading collision, which is a
naming hazard for a split rather than a content dependency.

The two Acceptance Criteria blocks are 100% inbound-dependent, 13 of 13 bullets. The pre-push gate
is legislated in four sections at once. 5-Serverless and 6-Observability define terms for each
other in both directions. None of this is visible to an explicit-phrase regex, which is why the
previous version reported a clean seam.

**This does not block the prune.** Most of these couplings are defects the prune should remove
rather than constraints it must preserve. Reconciling the checklists, merging the AC blocks into
what they test, and deleting the amendment log each reduce both word count and coupling. The
correct sequencing is repair first, split second, and the split should be re-evaluated against a
fresh map after F1.

## Prerequisites for any split

Each is a repair, and each reduces word count. Confirmed against the document, not assumed.

1. **Delete the amendment log (L578-588), the version footer (L635), and the L576 sentence that
   points at the footer, as one atomic change.** Deleting the footer alone leaves L576 dangling.
   Removes 13 of the 13 by-name pointers and roughly 210 words.
2. **Merge each Acceptance Criteria block into the section it tests.** Neither stands alone.
   Resolves 13 outbound bullets and 2 of the 8 heading collisions.
3. **Reconcile the two pre-push checklists to one.** Keep L619 on the conformance evidence above,
   delete L411-417, and fold L409(d)'s feature-branch requirement into the survivor.
4. **Resolve the L47 / L380 schema divergence to a single definition.**
5. **Normalise the two invisible headings at L96 and L104 before any tooling-driven split.**
   Carried forward unchanged. Trap 3 stands: `ExpressionAttributeNames` sits at L99 inside the
   first of them, and a split that runs before normalisation loses it.
6. **Define or delete the three dangling policy references** at L399, L48 and L131.

## Criterion 3 is not judgeable as written

The definition of done specifies grepping for `was `, `previously`, `superseded`, `updated to`,
`no longer`, `formerly`. Run against the current document that returns **one match**, L546
`**Root Cause**: Why this debt was introduced`, which is a template field name.

Precision 0 of 1. Recall 0: it sees none of the six amendment entries, not the version footer, and
not the "(updated)" supersession marker. The residue in this document is structural, not lexical.
A detector scoring zero on both axes is not a detector, and criterion 3 cannot be judged with it.

**Replacement:** `specs/001-constitution-prune/checks/residue-check.sh`, six rules, exit 1 on any
hit. Dated change entries, version identifiers, supersession markers in headings, past-tense edit
narration, the original word list kept as a subset, and migration leftovers scoped to a tool
vocabulary.

Against the amended constitution it reports **15 hits across 9 distinct lines**: the 6 amendment
entries at L578-588 (each matching two rules, hence 12 of the 15 hits), the version footer at
L635, the "(updated)" marker at L619, and the L546 template field. The `# Format (or black)`
migration leftover at L414 was removed by the 31 July amendment, which is why this is 15 and not 16.

**Criterion 8 demonstration.** Each of the six rules has been observed failing on an induced
perturbation, and the check reaches a genuine clean exit 0 on a repaired document:

| Run | Input | Expected | Result |
|---|---|---|---|
| 1 | constitution as measured | fail | exit 1, 16 hits (15 after the amendment) |
| 2 | amendment log, footer, markers removed | pass | exit 1, L546 only |
| 2b | run 2 plus L546 reworded to "origin of the debt" | pass | **exit 0, clean** |
| 3 | run 2b + `Amendment 1.7 (2026-07-31): Clarified ...` | fail | exit 1, dated-change-entry |
| 4a | run 2b + `**Version**: 1.7 \| **Ratified**: 2026-07-31` | fail | exit 1, version-identifier |
| 4b | run 2b + `Pre-Push Checklist (revised)` | fail | exit 1, supersession-marker |
| 4c | run 2b + `Removed the legacy adapter path.` | fail | exit 1, edit-narration |
| 4d | run 2b + `This rule was previously optional.` | fail | exit 1, residue-phrase |
| 4e | run 2b + `# Format (or black)` | fail | exit 1, migration-leftover |

Run 2 is the useful one. It shows the check refusing to go green on a document that still carries
a residue phrase, which is what forces the L546 reword rather than a suppression comment.

One known imprecision, stated rather than suppressed: the inherited `was ` rule fires on any
past-tense prose. L546 is its only current hit and the prune reworks that line anyway.

## Corrections to the previous version

| Previous claim | Corrected |
|---|---|
| Zero cross-section references; seam test passes decisively | 13 by-name pointers, plus couplings from 6 other strategies. Seam fails as-is. |
| Every large deletion candidate has zero inbound references | L635 has an inbound pointer from L576, quoted in the previous version's own text |
| Two heading styles are invisible (L96, L104) | Carried forward for the split constraint; the refutation found 22 bare pseudo-headings in total |
| 11-term table, `model_version` and SAST cross-cutting | Full-vocabulary sweep: both rank outside the top 13 by span |
| Residue is concentrated in the amendment log; grep returns 1 false positive | Count correct, conclusion wrong. The grep cannot see the amendment log at all. |
| SAST 14 hits | 15 hits, 5 sections. Section count was right. |
| `dashboard` 5 sections | Confirmed. 23 exact-word hits, 25 counting `dashboards` and `dashboard_api`. |
