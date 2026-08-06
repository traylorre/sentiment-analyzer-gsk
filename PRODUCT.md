# Sentiment Analyzer Product

> **CANON**: verified against code.

What the product is supposed to do, for whom. Implementation lives in the code and in
`docs/SERVICE-SHAPE.md`; rules that bind changes live in `.specify/memory/constitution.md`.

## What it does

Scores the sentiment of financial news per stock ticker and presents it to users as dashboards,
live updates, alerts, and email digests. News comes from external financial publishers on a fixed
polling cadence; users choose which tickers they care about and the product keeps those views
current.

## Who uses it

| Role | What they get |
|---|---|
| `anonymous` | A working dashboard with no signup. Session-based, upgradeable in place. |
| `free` | A persistent account via email magic link or OAuth. Anonymous work merges in on upgrade. |
| `paid` | Higher quotas on configurations and alerts. |
| `operator` | The admin dashboard: service metrics, articles, tickers, chaos experiments. |

Roles are strictly additive: everything a lower tier can do, a higher tier can do.

## Use cases

1. **Track a ticker watchlist.** A user creates a configuration naming the tickers they follow.
   The dashboard shows current sentiment per ticker, sentiment history, a heatmap across the
   watchlist, cross-ticker correlation, volatility, and premarket context. Configurations can be
   listed, edited, and deleted. Per-role quotas cap how many a user may hold, and hitting the cap
   is reported explicitly rather than failing silently.
2. **Watch sentiment move live.** An open dashboard receives sentiment updates as a live stream
   without the user reloading. Live events must always reflect the newest scored data.
3. **Get alerted on sentiment conditions.** A user attaches alert rules to a configuration,
   toggles them on and off, and receives an email when a rule fires. Email volume is quota-bound
   and the user can inspect remaining quota.
4. **Control email.** Users manage notification preferences and digests, unsubscribe from a link
   in any email, resubscribe, or disable everything at once.
5. **Find tickers.** Users search for tickers by name or symbol and validate a symbol before
   adding it to a configuration.
6. **See market context.** The dashboard shows whether the market is open and pairs sentiment
   with price history for the same tickers.
7. **Operate the service.** An operator views service-level metrics, recent articles, and ticker
   coverage on a separate admin dashboard, and runs controlled chaos experiments with reports.

## Success criteria

- An anonymous visitor reaches a functioning dashboard without creating an account.
- A user who signs up after working anonymously keeps that prior work.
- A new article from a covered publisher appears scored on the dashboard of every configuration
  containing its ticker, within the freshness bound below.
- Every scored article carries a sentiment label and score; the record schema is governed by
  `docs/MODELING.md`.
- An alert whose condition is met produces exactly one email for that firing, within quota.
- A request that exceeds a quota returns a distinct, user-visible quota error.
- An operator can see current service health without access to any customer's identity.

## Freshness and latency expectations

These bounds are the contract any caching layer is mapped against.

- **Ingestion cadence is 5 minutes.** Publishers are polled on that schedule; there is no push
  ingestion. A new article is expected to be scored and visible within one cycle of being polled.
- **The dashboard grades its own data age.** Data up to one cadence interval old is fresh, older
  than two intervals is stale, older than four is critical, and the user sees which state they
  are in. A cache may never serve data the dashboard would grade worse than fresh.
- **Live updates are deliberately not cached.** The sentiment stream bypasses every cache; each
  event reaches the client directly. Authenticated streams additionally forbid storage anywhere
  along the path.
- **Users can force freshness.** A configuration exposes an on-demand refresh, and the user can
  observe the refresh status while it runs.
- **History is bounded at 30 days.** Scored items expire after 30 days, so history views promise
  at most that window.
