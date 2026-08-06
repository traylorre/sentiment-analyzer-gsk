# Interview Demo Kit

> **CANON**: verified against code.

`interview/` holds interactive tooling for demonstrating this system's architecture in a
technical interview: a browser dashboard for the walkthrough and a script that generates
synthetic traffic against a deployed environment.

## Contents

| File | What it is |
|---|---|
| `interview/index.html` | Single-page demo dashboard. Environment toggle (preprod/prod), an interview timer, live API calls from the browser, and an architecture walkthrough. Open it directly or serve it with `python -m http.server` from `interview/`. |
| `interview/traffic_generator.py` | Synthetic traffic generator. `python3 traffic_generator.py --env preprod --scenario all` runs every scenario; individual scenarios cover the happy-path session flow, price-plus-sentiment shape validation, cache warmup latency, concurrent load, rate-limit 429 behavior, and circuit-breaker behavior. `--users` and `--requests` size the load scenario. |

## Cautions

The kit's talking points (costs, cache hit rates, test counts, circuit breaker thresholds) are
baked into the HTML and script, not generated from the code. Check them against the current
codebase before quoting any in a live demo.
