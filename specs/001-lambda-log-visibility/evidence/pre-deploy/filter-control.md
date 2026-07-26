# T005 Metric-Filter Positive Control (R-9) — BLOCKED by IAM, partial read-only evidence

Collected: 2026-07-26 (UTC), pre-deploy. AWS identity:
`arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer` (us-east-1).

## Planned control

Create log stream `feature-001-filter-control-test` in
`/aws/lambda/preprod-sentiment-dashboard`, put three ERROR-shaped messages with
event timestamps in distinct 60s buckets, then read
`SentimentAnalyzer/Packaging / DashboardImportErrors` at period=60 to attribute any
increment to a specific shape. Messages prepared:

1. Task-prescribed runtime-guess shape:
   `[ERROR] 2026-07-26T02:00:00.000Z 00000000-0000-0000-0000-000000000000 Runtime.ImportModuleError: Unable to import module 'handler'`
2. Filter-assumed field order (time first):
   `2026-07-26T02:00:01.000Z 00000000-0000-0000-0000-000000000000 ERROR Runtime.ImportModuleError: test`
3. Actual runtime shape as observed live in `/aws/lambda/preprod-sentiment-metrics`
   during T003 (added because ground truth became available):
   `[ERROR] Runtime.ImportModuleError: Unable to import module 'handler': No module named 'aws_lambda_powertools'`

## Denials (verbatim)

`logs:CreateLogStream`:

```
AccessDeniedException: User: arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer
is not authorized to perform: logs:CreateLogStream on resource:
arn:aws:logs:us-east-1:218795110243:log-group:/aws/lambda/preprod-sentiment-dashboard:log-stream:feature-001-filter-control-test
because no identity-based policy allows the logs:CreateLogStream action
```

Fallback attempt via the read-only `logs:TestMetricFilter` API (evaluates a pattern
against sample messages, touches no resources) — also denied:

```
AccessDeniedException: User: arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer
is not authorized to perform: logs:TestMetricFilter ... because no identity-based
policy allows the logs:TestMetricFilter action
```

No privilege escalation attempted. No test stream was created; nothing to clean up.

## Read-only evidence gathered instead

1. Filter is deployed exactly as coded (`describe-metric-filters` on the dashboard
   group): name `preprod-sentiment-dashboard-import-errors`, pattern
   `[time, request_id, level=ERROR*, msg="*ImportModuleError*" || msg="*No module named*" || msg="*cannot import name*"]`,
   created 2025-12-06T07:48:01Z, `applyOnTransformedLogs: false`.
2. `list-metrics --namespace SentimentAnalyzer/Packaging` returns **empty** — the
   `DashboardImportErrors` metric has never been created, i.e. the filter has never
   matched a single event since deployment. 14-day `get-metric-statistics` (Sum,
   daily): no datapoints.
3. Caveat that keeps (2) from being conclusive on its own: the dashboard log group
   contains zero `ImportModuleError` / `No module named` / ERROR-token lines in the
   last 7 days (dashboard Lambda is healthy), so "no metric" could also mean
   "no error ever offered to the filter" over that window at least.
4. Ground-truth error shape (live, from the metrics-Lambda crash loop, see
   `metrics-dup-baseline.md`): the runtime emits
   `[ERROR] Runtime.ImportModuleError: <msg>` — **`[ERROR]` is the first
   space-delimited token; there is no leading timestamp or request-id**.

## Static field-alignment analysis (pattern vs shapes)

Space-delimited pattern fields: `time` (1st), `request_id` (2nd), `level=ERROR*`
(3rd), `msg=...` (4th).

| shape | field 3 content | matches `level=ERROR*` in field 3? |
|---|---|---|
| real runtime (`[ERROR] Runtime.ImportModuleError: Unable ...`) | `Unable` | no |
| task msg 1 (`[ERROR] <time> <rid> Runtime.ImportModuleError...`) | `<rid>` | no |
| task msg 2 (`<time> <rid> ERROR Runtime.ImportModuleError: test`) | `ERROR` | field 3 aligns, but per AWS docs a space-delimited pattern with 4 terms requires a 4-term event unless `...` is used; msg 2 has 5 tokens — match is uncertain without a live test |

The runtime never emits shape 2; shapes 1 and 3 (the only real ones) cannot satisfy
`level=ERROR*` in field position 3.

## Verdict

**R-9: filter is dead-on-arrival with high confidence, but the live positive control
is UNPROVEN — blocked by IAM.** Evidence: (a) the pattern's field positions cannot
align with the runtime's actual `[ERROR] Runtime.ImportModuleError: ...` shape,
(b) the metric has never existed in 7+ months of the filter being deployed, and
(c) a real, week-old ImportModuleError crash loop in the metrics Lambda raised no
alarm (though that group isn't watched by this filter — the coverage gap is itself a
finding). To close R-9 conclusively, re-run this control at/after T024 with either
`logs:CreateLogStream`+`logs:PutLogEvents` or `logs:TestMetricFilter` granted, or
have the orchestrator run the three prepared messages above from a principal that
has those permissions.
