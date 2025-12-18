"""Configuration lookup for SSE streaming Lambda.

Provides configuration retrieval from DynamoDB for config-specific streams.
Per T033: Implement config lookup to validate user access and get ticker filters.
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

from src.lambdas.shared.logging_utils import sanitize_for_log
from src.lambdas.shared.models.configuration import Configuration

logger = logging.getLogger(__name__)


class ConfigLookupService:
    """Lookup user configurations from DynamoDB.

    Used to validate that:
    1. The configuration exists
    2. The user owns the configuration
    3. Get ticker filters for stream filtering
    """

    def __init__(self, table_name: str | None = None):
        """Initialize config lookup service.

        Args:
            table_name: DynamoDB table name.
                       Defaults to DATABASE_TABLE env var (required).
        """
        # Use DATABASE_TABLE (Feature 006 users table) where configs are stored.
        # Dashboard Lambda uses the same pattern in router_v2.py.
        self._table_name = table_name or os.environ["DATABASE_TABLE"]
        self._table = None  # Lazy initialization

    def _get_table(self):
        """Get DynamoDB table resource (lazy initialization)."""
        if self._table is None:
            dynamodb = boto3.resource("dynamodb")
            self._table = dynamodb.Table(self._table_name)
        return self._table

    def get_configuration(self, user_id: str, config_id: str) -> Configuration | None:
        """Get a configuration by user ID and config ID.

        Args:
            user_id: User ID from X-User-ID header
            config_id: Configuration ID from URL path

        Returns:
            Configuration if found and active, None otherwise
        """
        try:
            table = self._get_table()
            response = table.get_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"CONFIG#{config_id}",
                }
            )

            item = response.get("Item")
            if not item:
                logger.debug(
                    "Configuration not found",
                    extra={
                        "config_id": sanitize_for_log(
                            config_id[:8] if config_id else ""
                        ),
                        "user_id_prefix": sanitize_for_log(
                            user_id[:8] if user_id else ""
                        ),
                    },
                )
                return None

            # Check if configuration is active (not soft-deleted)
            if not item.get("is_active", True):
                logger.debug(
                    "Configuration is inactive",
                    extra={
                        "config_id": sanitize_for_log(
                            config_id[:8] if config_id else ""
                        )
                    },
                )
                return None

            config = Configuration.from_dynamodb_item(item)
            logger.debug(
                "Configuration found",
                extra={
                    "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
                    "ticker_count": len(config.tickers),
                },
            )
            return config

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(
                "DynamoDB get_item failed",
                extra={
                    "error": str(e),
                    "error_code": error_code,
                    "error_message": error_message,
                    "table_name": self._table_name,
                    "operation": "get_item",
                    "config_id": sanitize_for_log(config_id[:8] if config_id else ""),
                    "user_id_prefix": sanitize_for_log(user_id[:8] if user_id else ""),
                },
            )
            return None

    def get_ticker_filters(self, user_id: str, config_id: str) -> list[str] | None:
        """Get ticker symbols for a configuration.

        Convenience method for stream filtering.

        Args:
            user_id: User ID from X-User-ID header
            config_id: Configuration ID from URL path

        Returns:
            List of ticker symbols if config found, None otherwise
        """
        config = self.get_configuration(user_id, config_id)
        if config is None:
            return None

        return [ticker.symbol for ticker in config.tickers]

    def validate_user_access(
        self, user_id: str, config_id: str
    ) -> tuple[bool, list[str] | None]:
        """Validate user has access to configuration and get tickers.

        Combined lookup for efficiency - single DynamoDB call.

        Args:
            user_id: User ID from X-User-ID header
            config_id: Configuration ID from URL path

        Returns:
            Tuple of (has_access, ticker_symbols).
            If has_access is False, ticker_symbols is None.
        """
        config = self.get_configuration(user_id, config_id)
        if config is None:
            return False, None

        # User owns this configuration (verified by PK = USER#{user_id})
        return True, [ticker.symbol for ticker in config.tickers]


# Global config lookup service instance
config_lookup_service = ConfigLookupService()
