"""Configuration CRUD endpoints for Feature 006.

Implements configuration management (T049-T053):
- POST /api/v2/configurations - Create configuration
- GET /api/v2/configurations - List configurations
- GET /api/v2/configurations/{id} - Get configuration
- PATCH /api/v2/configurations/{id} - Update configuration
- DELETE /api/v2/configurations/{id} - Delete configuration

For On-Call Engineers:
    Configurations are stored with PK=USER#{user_id}, SK=CONFIG#{config_id}.
    Users can have max 2 configurations.
    Each configuration can have max 5 tickers.

Security Notes:
    - All operations require valid user session
    - Users can only access their own configurations
    - Ticker symbols are validated before storage
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from boto3.dynamodb.conditions import Key
from pydantic import BaseModel

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lambdas.shared.models.configuration import (
    CONFIG_LIMITS,
    Configuration,
    ConfigurationCreate,
    ConfigurationUpdate,
    Ticker,
)

logger = logging.getLogger(__name__)


# Response schemas


class TickerResponse(BaseModel):
    """Ticker info in configuration response."""

    symbol: str
    name: str | None
    exchange: str


class ConfigurationResponse(BaseModel):
    """Configuration response."""

    config_id: str
    name: str
    tickers: list[TickerResponse]
    timeframe_days: int
    include_extended_hours: bool
    created_at: str
    updated_at: str | None = None


class ConfigurationListResponse(BaseModel):
    """Response for GET /api/v2/configurations."""

    configurations: list[ConfigurationResponse]
    max_allowed: int = CONFIG_LIMITS["max_configs_per_user"]


class ErrorDetail(BaseModel):
    """Error detail for validation errors."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail


# Service functions


def create_configuration(
    table: Any,
    user_id: str,
    request: ConfigurationCreate,
    ticker_cache: Any | None = None,
) -> ConfigurationResponse | ErrorResponse:
    """Create a new configuration.

    Args:
        table: DynamoDB Table resource
        user_id: User ID (from session)
        request: Configuration creation request
        ticker_cache: Optional ticker cache for validation

    Returns:
        ConfigurationResponse on success, ErrorResponse on failure
    """
    # Check if user has reached max configurations
    existing_count = _count_user_configurations(table, user_id)
    if existing_count >= CONFIG_LIMITS["max_configs_per_user"]:
        return ErrorResponse(
            error=ErrorDetail(
                code="CONFLICT",
                message=f"Maximum configurations ({CONFIG_LIMITS['max_configs_per_user']}) reached",
            )
        )

    # Validate tickers
    validated_tickers = []
    for symbol in request.tickers:
        ticker_info = _validate_ticker(symbol, ticker_cache)
        if ticker_info is None:
            return ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_TICKER",
                    message=f"Invalid ticker symbol: {symbol}",
                    details={
                        "field": "tickers",
                        "constraint": "must be valid US stock symbol",
                    },
                )
            )
        validated_tickers.append(ticker_info)

    now = datetime.now(UTC)
    config_id = str(uuid.uuid4())

    config = Configuration(
        config_id=config_id,
        user_id=user_id,
        name=request.name,
        tickers=validated_tickers,
        timeframe_days=request.timeframe_days,
        include_extended_hours=request.include_extended_hours,
        atr_period=14,  # Default
        created_at=now,
        updated_at=now,
        is_active=True,
    )

    try:
        table.put_item(Item=config.to_dynamodb_item())

        logger.info(
            "Created configuration",
            extra={
                "config_id": sanitize_for_log(config_id[:8]),
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "ticker_count": len(validated_tickers),
            },
        )

        return _config_to_response(config)

    except Exception as e:
        logger.error(
            "Failed to create configuration",
            extra=get_safe_error_info(e),
        )
        raise


def list_configurations(
    table: Any,
    user_id: str,
) -> ConfigurationListResponse:
    """List user's configurations.

    Args:
        table: DynamoDB Table resource
        user_id: User ID

    Returns:
        ConfigurationListResponse with all user configurations
    """
    try:
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with("CONFIG#"),
        )

        configs = []
        for item in response.get("Items", []):
            if item.get("is_active", True):
                config = Configuration.from_dynamodb_item(item)
                configs.append(_config_to_response(config))

        # Sort by created_at descending
        configs.sort(key=lambda c: c.created_at, reverse=True)

        logger.debug(
            "Listed configurations",
            extra={
                "user_id_prefix": sanitize_for_log(user_id[:8]),
                "count": len(configs),
            },
        )

        return ConfigurationListResponse(
            configurations=configs,
            max_allowed=CONFIG_LIMITS["max_configs_per_user"],
        )

    except Exception as e:
        logger.error(
            "Failed to list configurations",
            extra=get_safe_error_info(e),
        )
        raise


def get_configuration(
    table: Any,
    user_id: str,
    config_id: str,
) -> ConfigurationResponse | None:
    """Get a single configuration.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        config_id: Configuration ID

    Returns:
        ConfigurationResponse if found, None otherwise
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": f"CONFIG#{config_id}",
            }
        )

        item = response.get("Item")
        if not item:
            return None

        if not item.get("is_active", True):
            return None

        config = Configuration.from_dynamodb_item(item)
        return _config_to_response(config)

    except Exception as e:
        logger.error(
            "Failed to get configuration",
            extra={
                "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
                **get_safe_error_info(e),
            },
        )
        raise


def update_configuration(
    table: Any,
    user_id: str,
    config_id: str,
    request: ConfigurationUpdate,
    ticker_cache: Any | None = None,
) -> ConfigurationResponse | ErrorResponse | None:
    """Update an existing configuration.

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        config_id: Configuration ID
        request: Update request
        ticker_cache: Optional ticker cache for validation

    Returns:
        ConfigurationResponse on success, ErrorResponse on validation error,
        None if configuration not found
    """
    # Get existing configuration
    existing = get_configuration(table, user_id, config_id)
    if existing is None:
        return None

    # Build update expression
    update_parts = []
    attr_values: dict[str, Any] = {}

    if request.name is not None:
        update_parts.append("name = :name")
        attr_values[":name"] = request.name

    if request.tickers is not None:
        # Validate new tickers
        validated_tickers = []
        for symbol in request.tickers:
            ticker_info = _validate_ticker(symbol, ticker_cache)
            if ticker_info is None:
                return ErrorResponse(
                    error=ErrorDetail(
                        code="INVALID_TICKER",
                        message=f"Invalid ticker symbol: {symbol}",
                    )
                )
            validated_tickers.append(ticker_info)

        update_parts.append("tickers = :tickers")
        attr_values[":tickers"] = [t.model_dump() for t in validated_tickers]

    if request.timeframe_days is not None:
        update_parts.append("timeframe_days = :timeframe")
        attr_values[":timeframe"] = request.timeframe_days

    if request.include_extended_hours is not None:
        update_parts.append("include_extended_hours = :extended")
        attr_values[":extended"] = request.include_extended_hours

    # Always update updated_at
    now = datetime.now(UTC)
    update_parts.append("updated_at = :updated")
    attr_values[":updated"] = now.isoformat()

    if not update_parts:
        # Nothing to update, return existing
        return existing

    try:
        table.update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": f"CONFIG#{config_id}",
            },
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeValues=attr_values,
        )

        logger.info(
            "Updated configuration",
            extra={
                "config_id": sanitize_for_log(config_id[:8]),
                "updated_fields": list(attr_values.keys()),
            },
        )

        # Return updated configuration
        return get_configuration(table, user_id, config_id)

    except Exception as e:
        logger.error(
            "Failed to update configuration",
            extra=get_safe_error_info(e),
        )
        raise


def delete_configuration(
    table: Any,
    user_id: str,
    config_id: str,
) -> bool:
    """Delete a configuration (soft delete).

    Args:
        table: DynamoDB Table resource
        user_id: User ID
        config_id: Configuration ID

    Returns:
        True if deleted, False if not found
    """
    # Verify configuration exists and belongs to user
    existing = get_configuration(table, user_id, config_id)
    if existing is None:
        return False

    try:
        # Soft delete by setting is_active = False
        table.update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": f"CONFIG#{config_id}",
            },
            UpdateExpression="SET is_active = :inactive, updated_at = :updated",
            ExpressionAttributeValues={
                ":inactive": False,
                ":updated": datetime.now(UTC).isoformat(),
            },
        )

        logger.info(
            "Deleted configuration",
            extra={
                "config_id": sanitize_for_log(config_id[:8]),
                "user_id_prefix": sanitize_for_log(user_id[:8]),
            },
        )

        return True

    except Exception as e:
        logger.error(
            "Failed to delete configuration",
            extra=get_safe_error_info(e),
        )
        raise


# Helper functions


def _count_user_configurations(table: Any, user_id: str) -> int:
    """Count user's active configurations."""
    try:
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with("CONFIG#"),
            Select="COUNT",
            FilterExpression="is_active = :active",
            ExpressionAttributeValues={":active": True},
        )
        return response.get("Count", 0)
    except Exception:
        return 0


def _validate_ticker(symbol: str, ticker_cache: Any | None) -> Ticker | None:
    """Validate ticker symbol and return Ticker object.

    Args:
        symbol: Ticker symbol (e.g., "AAPL")
        ticker_cache: Optional ticker cache for validation

    Returns:
        Ticker if valid, None otherwise
    """
    symbol = symbol.upper().strip()

    # Basic format validation
    if not symbol or len(symbol) > 5:
        return None

    if not symbol.isalpha():
        return None

    # If we have a ticker cache, validate against it
    if ticker_cache:
        validation = ticker_cache.validate(symbol)
        if validation.get("status") != "valid":
            return None

        return Ticker(
            symbol=symbol,
            name=validation.get("name"),
            exchange=validation.get("exchange", "NASDAQ"),
            added_at=datetime.now(UTC),
        )

    # Without cache, accept common exchanges (for testing)
    # In production, ticker_cache should always be provided
    return Ticker(
        symbol=symbol,
        name=f"{symbol} Inc",  # Placeholder
        exchange="NASDAQ",  # Default
        added_at=datetime.now(UTC),
    )


def _config_to_response(config: Configuration) -> ConfigurationResponse:
    """Convert Configuration to response format."""
    return ConfigurationResponse(
        config_id=config.config_id,
        name=config.name,
        tickers=[
            TickerResponse(
                symbol=t.symbol,
                name=t.name,
                exchange=t.exchange,
            )
            for t in config.tickers
        ],
        timeframe_days=config.timeframe_days,
        include_extended_hours=config.include_extended_hours,
        created_at=config.created_at.isoformat().replace("+00:00", "Z"),
        updated_at=config.updated_at.isoformat().replace("+00:00", "Z")
        if config.updated_at
        else None,
    )
