"""Utility functions for shared Lambda code."""

from src.lambdas.shared.utils.cookie_helpers import make_set_cookie, parse_cookies
from src.lambdas.shared.utils.dedup import (
    generate_dedup_key,
    generate_dedup_key_from_article,
)
from src.lambdas.shared.utils.event_helpers import (
    get_header,
    get_path_params,
    get_query_params,
)
from src.lambdas.shared.utils.event_validator import (
    InvalidEventError,
    validate_apigw_event,
)
from src.lambdas.shared.utils.market import get_cache_expiration, is_market_open
from src.lambdas.shared.utils.payload_guard import check_response_size
from src.lambdas.shared.utils.response_builder import (
    error_response,
    json_response,
    validation_error_response,
)
from src.lambdas.shared.utils.url_decode import decode_path_param

__all__ = [
    "check_response_size",
    "decode_path_param",
    "error_response",
    "generate_dedup_key",
    "generate_dedup_key_from_article",
    "get_cache_expiration",
    "get_header",
    "get_path_params",
    "get_query_params",
    "InvalidEventError",
    "is_market_open",
    "json_response",
    "make_set_cookie",
    "parse_cookies",
    "validate_apigw_event",
    "validation_error_response",
]
