# Data and model requirements

> **CANON**: verified against code.

A pending schema-change proposal for streaming subscriptions (adjacency-list pattern, affects
table schema, caching, and routes) sits in `docs/dynamodb-schema-change-quarrysome.md`; it is
QUARRYSOME until the schema comb adjudicates it.

The inference path, what is actually persisted, and retention. Architecture is in
`docs/SERVICE-SHAPE.md`.

## The persisted item is a dict, not a Pydantic model

This is the trap. `src/lambdas/shared/models/news_item.py` and `sentiment_result.py` look
authoritative and are not on any live path. `NewsItem` is constructed only in
`src/lambdas/ingestion/storage.py`, whose entry points `store_news_items()` and
`store_news_items_with_notification()` have zero callers in `src/`. `SentimentResult` is never
constructed anywhere in `src/`. Both are exercised only by unit tests.

What is actually written is a plain dict, assembled in two stages and keyed `source_id` /
`timestamp`:

- Ingestion builds it at `src/lambdas/ingestion/handler.py:991` and merges it into the upsert at
  `src/lambdas/ingestion/dedup.py:244`. Fields: `source_id` (`dedup:{dedup_key}`), `timestamp`,
  `dedup_key`, `sources` (a list), `source_attribution` (a map), `created_at`, `updated_at`,
  `headline`, `normalized_headline`, `source_url`, `text_snippet`, `text_for_analysis`, `status`,
  `matched_tickers`, `ttl_timestamp`, `metadata`.
- Analysis then sets four flat attributes on the same item:
  `sentiment`, `score`, `model_version`, `status` (`src/lambdas/analysis/handler.py:326`).

There is no `result_id`, no `sentiment_label`, no `confidence`, and no nested source object on the
stored record. The read path builds its own shape again in `SourceSentiment`
(`src/lambdas/dashboard/sentiment.py:164`), which is what `/api/v2/configurations/{id}/sentiment`
returns.

At least five Pydantic models in this repo describe overlapping sentiment records with different
field names. Two of them are both called `SentimentScore` and have different shapes:
`src/lambdas/shared/models/news_item.py:13` (`score`, `confidence`, `label`) and
`src/lib/timeseries/models.py:68` (`value`, `timestamp`, `label`, `ticker`, `source`, no
confidence). The timeseries one is the one on the live analysis path. Check the import, not the
name.

## Score is a probability, and its sign lives elsewhere

`score` as persisted is DistilBERT's confidence in its own label, roughly `0.5` to `1.0`, returned
unchanged at `src/lambdas/analysis/sentiment.py:274`. Direction is carried by the separate
`sentiment` string (`positive` / `negative` / `neutral`), assigned by thresholding that same score.

The Pydantic models declare `score` with `ge=-1.0, le=1.0`, so a signed range is legal in the type
and never produced by the live scorer. Do not infer from the model declaration that negative scores
appear in stored data.

On the API response, `confidence` is a duplicate of `score`
(`src/lambdas/analysis/handler.py:215`), set only to satisfy a contract test.

## Raw text is persisted

Two fields, both written on every article, with no approval gate:

- `text_snippet`, truncated to 200 characters.
- `text_for_analysis`, which is `f"{title}. {description}"` and is **not truncated** when both are
  present (`src/lambdas/ingestion/handler.py:1060`). Only the description-only fallback truncates.

If you need raw publisher text not to be stored, that is a change to make, not a rule to cite.

## Retention

30 days, via DynamoDB TTL. `TTL_DAYS` at `src/lambdas/ingestion/handler.py:136`, stamped onto
`ttl_timestamp` at `:988`, with the table's TTL attribute configured in
`infrastructure/terraform/modules/dynamodb/main.tf`.

## Model versioning

`model_version` does not identify a model. It is the CI git artifact SHA, set as an environment
variable at `.github/workflows/deploy.yml:1570`, read by ingestion, passed through SNS, and written
by analysis as a label. The analysis Lambda never consults it when scoring.

The model itself is a hardcoded constant, `DEFAULT_MODEL_S3_KEY = "distilbert/v1.0.0/model.tar.gz"`
at `src/lambdas/analysis/sentiment.py:59`, downloaded from S3 at cold start. The bucket is
overridable by `MODEL_S3_BUCKET`; the key is not. Changing `MODEL_VERSION` changes the stored label
and loads the identical model. There is no model changelog.

## Re-running inference is not supported

There is no replay, rescore or backfill path in `src/`. The analysis write is guarded by
`ConditionExpression="#status = :pending"` and flips status to `analyzed`
(`src/lambdas/analysis/handler.py:340`), so a re-delivered item is rejected rather than re-scored.
Re-scoring an already-scored item requires a code change.

`source_id` and the fetch timestamp are recorded, so the inputs for a replay exist. The mechanism
does not.
