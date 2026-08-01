# Data and model requirements

Detail extracted from the constitution. Needed when working on the inference path, the output
contract, or model deployment.

## Output schema

There is no single output schema. Two Pydantic models describe overlapping records with different
field names, and both are authoritative for their own path:

- `src/lambdas/shared/models/news_item.py` is an ingested article. Keyed by `dedup_key`, with
  `source` as a bare `Literal["tiingo","finnhub"]` and sentiment nested under a `SentimentScore`
  (`score`, `confidence`, `label`).
- `src/lambdas/shared/models/sentiment_result.py` is a scoring result. Keyed by `result_id`, with
  flat `sentiment_score` / `sentiment_label` / `confidence` and `source` as a nested
  `SentimentSource` (`source_type`, `inference_version` aliased `model_version`, `fetched_at`).

Read the model for the path you are on. Do not write prose copies of either shape; earlier copies
in this repo drifted from both.

Two range facts that catch people:

- `score` is **signed**, `-1.0` to `1.0` (`news_item.py:20`, `sentiment_result.py:27`). Negative
  values are ordinary output, not errors. Validation that assumes `0-1` rejects most real output.
- `confidence` is `0.0` to `1.0` in both, but **nullable in one and required in the other**:
  `news_item.py:21` is `float | None` (null for unscored sources such as Tiingo), while
  `sentiment_result.py:29` is a required `float`. Tests that assert a `None` case against
  `SentimentResult` will fail.

## Raw text retention

By default do NOT persist full raw text unless explicitly required and approved. If a
`text_snippet` is stored it must be minimal (for example the first N characters) and the storage
policy must be documented.

## Model versioning

Every deployed model must have a version string and a changelog.

## Reproducibility

Inference must be re-runnable against a specified `model_version` and configuration. Record the
source item id and the fetch timestamp so replays are possible.
