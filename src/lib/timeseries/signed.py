"""
Signed sentiment mapping.

Single source of truth for converting a sentiment label plus model confidence
into a signed contribution in [-1, 1]. Used by the analysis handler at the
fanout hop, the backfill recompute, and the test oracle; divergent copies of
this mapping are how buckets and readers ended up on different sign
conventions.

Import constraint: the SSE image copies src/lib/timeseries as a whole
directory but top-level src/lib files individually, so this module must not
import any top-level src/lib module other than metrics.py (research D2).
"""


def label_to_signed(label: str, confidence: float) -> float:
    """
    Map a sentiment label and confidence to a signed contribution in [-1, 1].

    positive -> +confidence, negative -> -confidence, anything else -> 0.0.
    """
    if label == "positive":
        return confidence
    if label == "negative":
        return -confidence
    return 0.0
