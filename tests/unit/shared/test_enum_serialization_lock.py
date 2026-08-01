"""Serialization lock tests for the 7 UP042-suppressed (str, Enum) classes.

Tripwire against accidental StrEnum conversion; the migration is carded on
CLEANUP-BOARD.html. These enums are serialized into
DynamoDB items and JSON responses. Converting them to enum.StrEnum changes
str(member) from "ClassName.MEMBER" to the bare value, silently altering any
call site that relies on str()/f-string formatting. Each test asserts both
halves of the current contract:

- str(member) is the qualified "ClassName.MEMBER" form (str,Enum behavior)
- member.value is the exact wire string stored in DynamoDB/JSON

If a deliberate StrEnum migration lands, these
assertions must be updated in the same change, with a serialization sweep of
every call site.
"""

import pytest

from src.lambdas.analysis.sentiment import SentimentLabel, SentimentSource
from src.lambdas.shared.errors.auth_errors import AuthErrorCode
from src.lambdas.shared.middleware.auth_middleware import AuthType
from src.lambdas.shared.models.ohlc import OHLCResolution, TimeRange
from src.lib.timeseries.models import Resolution

EXPECTED_WIRE_VALUES = {
    Resolution: {
        "ONE_MINUTE": "1m",
        "FIVE_MINUTES": "5m",
        "FIFTEEN_MINUTES": "15m",
        "THIRTY_MINUTES": "30m",
        "ONE_HOUR": "1h",
        "TWENTY_FOUR_HOURS": "24h",
    },
    SentimentSource: {
        "TIINGO": "tiingo",
        "FINNHUB": "finnhub",
        "OUR_MODEL": "our_model",
    },
    SentimentLabel: {
        "POSITIVE": "positive",
        "NEGATIVE": "negative",
        "NEUTRAL": "neutral",
    },
    AuthErrorCode: {
        "AUTH_013": "AUTH_013",
        "AUTH_014": "AUTH_014",
        "AUTH_015": "AUTH_015",
        "AUTH_016": "AUTH_016",
        "AUTH_017": "AUTH_017",
        "AUTH_018": "AUTH_018",
    },
    AuthType: {
        "ANONYMOUS": "anonymous",
        "AUTHENTICATED": "authenticated",
    },
    TimeRange: {
        "ONE_WEEK": "1W",
        "ONE_MONTH": "1M",
        "THREE_MONTHS": "3M",
        "SIX_MONTHS": "6M",
        "ONE_YEAR": "1Y",
    },
    OHLCResolution: {
        "ONE_MINUTE": "1",
        "FIVE_MINUTES": "5",
        "FIFTEEN_MINUTES": "15",
        "THIRTY_MINUTES": "30",
        "ONE_HOUR": "60",
        "DAILY": "D",
    },
}


@pytest.mark.parametrize("enum_cls", EXPECTED_WIRE_VALUES, ids=lambda e: e.__name__)
class TestEnumSerializationLock:
    """Lock str() and .value for every member of every suppressed enum."""

    def test_member_census_is_exact(self, enum_cls):
        """No member added, removed, or renamed without updating this lock."""
        assert {m.name for m in enum_cls} == set(EXPECTED_WIRE_VALUES[enum_cls])

    def test_str_is_qualified_name(self, enum_cls):
        """str(member) keeps the (str, Enum) qualified form, not the bare value."""
        for member in enum_cls:
            assert str(member) == f"{enum_cls.__name__}.{member.name}"

    def test_value_is_wire_string(self, enum_cls):
        """member.value is the exact string persisted to DynamoDB/JSON."""
        expected = EXPECTED_WIRE_VALUES[enum_cls]
        for member in enum_cls:
            assert member.value == expected[member.name]
