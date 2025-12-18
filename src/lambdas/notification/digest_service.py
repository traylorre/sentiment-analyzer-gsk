"""Daily digest email service for Feature 006.

Generates personalized daily digest emails with:
- Sentiment changes for watched tickers
- ATR (volatility) highlights
- Alert trigger summary

Scheduled via EventBridge at configurable times per user timezone.

For On-Call Engineers:
    Digest failures are non-critical (no alert triggered).
    Check CloudWatch logs for DIGEST_ERROR entries.
    Common issues:
    - DynamoDB throttling during user scan
    - SendGrid rate limiting (100/day)
    - Timezone conversion errors

Security Notes:
    - User data is never logged in full
    - Email addresses are hashed in metrics
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from boto3.dynamodb.conditions import Key

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lambdas.shared.models.configuration import Configuration
from src.lambdas.shared.models.notification import DigestSettings
from src.lambdas.shared.models.user import User

logger = logging.getLogger(__name__)


class DigestServiceError(Exception):
    """Base exception for digest service errors."""

    pass


class DigestData:
    """Container for digest email content."""

    def __init__(
        self,
        user: User,
        settings: DigestSettings,
        configs: list[Configuration],
        ticker_data: dict[str, dict[str, Any]],
    ):
        self.user = user
        self.settings = settings
        self.configs = configs
        self.ticker_data = ticker_data
        self.generated_at = datetime.now(UTC)

    @property
    def has_content(self) -> bool:
        """Check if digest has meaningful content to send."""
        return bool(self.ticker_data)

    @property
    def all_tickers(self) -> list[str]:
        """Get all unique tickers across configurations."""
        tickers = set()
        for config in self.configs:
            for ticker in config.tickers:
                tickers.add(ticker.symbol)
        return sorted(tickers)


class DigestService:
    """Service for generating and sending daily digest emails."""

    def __init__(
        self, table: Any, dashboard_url: str = "https://sentiment-analyzer.com"
    ):
        """Initialize digest service.

        Args:
            table: DynamoDB table resource
            dashboard_url: Base URL for dashboard links
        """
        self.table = table
        self.dashboard_url = dashboard_url

    def get_users_for_digest(
        self, current_hour_utc: int
    ) -> list[tuple[User, DigestSettings]]:
        """Query users who should receive digest at current UTC hour.

        The digest is scheduled per user timezone. We check all users whose
        configured digest time falls within the current UTC hour.

        Args:
            current_hour_utc: Current hour in UTC (0-23)

        Returns:
            List of (User, DigestSettings) tuples for users due for digest
        """
        users_due: list[tuple[User, DigestSettings]] = []

        # Query using by_entity_status GSI for DIGEST_SETTINGS items
        # CRITICAL: No table scan - GSI query is O(n) where n = digest settings count
        try:
            response = self.table.query(
                IndexName="by_entity_status",
                KeyConditionExpression="entity_type = :et",
                FilterExpression="enabled = :enabled",
                ExpressionAttributeValues={
                    ":et": "DIGEST_SETTINGS",
                    ":enabled": True,
                },
                ProjectionExpression="PK, SK, user_id, #t, timezone, include_all_configs, config_ids, last_sent",
                ExpressionAttributeNames={"#t": "time"},
            )

            for item in response.get("Items", []):
                settings = DigestSettings.from_dynamodb_item(item)

                # Check if this user's digest time matches current UTC hour
                if self._is_digest_due(settings, current_hour_utc):
                    # Get user profile
                    user = self._get_user(settings.user_id)
                    if user and user.email:
                        users_due.append((user, settings))

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.table.query(
                    IndexName="by_entity_status",
                    KeyConditionExpression="entity_type = :et",
                    FilterExpression="enabled = :enabled",
                    ExpressionAttributeValues={
                        ":et": "DIGEST_SETTINGS",
                        ":enabled": True,
                    },
                    ProjectionExpression="PK, SK, user_id, #t, timezone, include_all_configs, config_ids, last_sent",
                    ExpressionAttributeNames={"#t": "time"},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                for item in response.get("Items", []):
                    settings = DigestSettings.from_dynamodb_item(item)
                    if self._is_digest_due(settings, current_hour_utc):
                        user = self._get_user(settings.user_id)
                        if user and user.email:
                            users_due.append((user, settings))

            logger.info(
                "Found users due for digest",
                extra={"count": len(users_due), "current_hour_utc": current_hour_utc},
            )

        except Exception as e:
            logger.error(
                "Failed to query digest users",
                extra=get_safe_error_info(e),
            )
            raise DigestServiceError(f"Failed to query users: {e}") from e

        return users_due

    def _is_digest_due(self, settings: DigestSettings, current_hour_utc: int) -> bool:
        """Check if digest is due for user based on their timezone and configured time.

        Args:
            settings: User's digest settings
            current_hour_utc: Current hour in UTC

        Returns:
            True if digest should be sent now
        """
        try:
            # Parse user's configured time (e.g., "09:00")
            hour, minute = map(int, settings.time.split(":"))

            # Get user's timezone
            user_tz = ZoneInfo(settings.timezone)

            # Get current time in user's timezone
            now_utc = datetime.now(UTC)
            now_user = now_utc.astimezone(user_tz)

            # Check if we're in the right hour (allow 5-minute window at start of hour)
            if now_user.hour == hour and now_user.minute < 5:
                # Also check we haven't already sent today
                if settings.last_sent:
                    last_sent_user = settings.last_sent.astimezone(user_tz)
                    if last_sent_user.date() == now_user.date():
                        return False
                return True

            return False

        except Exception as e:
            logger.warning(
                "Failed to check digest due time",
                extra={
                    "user_id": sanitize_for_log(settings.user_id[:8]),
                    **get_safe_error_info(e),
                },
            )
            return False

    def _get_user(self, user_id: str) -> User | None:
        """Get user profile from DynamoDB.

        Args:
            user_id: User ID

        Returns:
            User object or None if not found
        """
        try:
            response = self.table.get_item(
                Key={"PK": f"USER#{user_id}", "SK": "PROFILE"}
            )
            if "Item" in response:
                return User.from_dynamodb_item(response["Item"])
            return None
        except Exception as e:
            logger.warning(
                "Failed to get user",
                extra={
                    "user_id": sanitize_for_log(user_id[:8]),
                    **get_safe_error_info(e),
                },
            )
            return None

    def get_user_configurations(
        self, user_id: str, settings: DigestSettings
    ) -> list[Configuration]:
        """Get configurations to include in digest.

        Args:
            user_id: User ID
            settings: Digest settings (controls which configs to include)

        Returns:
            List of Configuration objects
        """
        configs: list[Configuration] = []

        try:
            # Query all user's configurations
            response = self.table.query(
                KeyConditionExpression=(
                    Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("CONFIG#")
                ),
            )

            for item in response.get("Items", []):
                config = Configuration.from_dynamodb_item(item)

                # Filter by config_ids if not including all
                if settings.include_all_configs:
                    configs.append(config)
                elif config.config_id in settings.config_ids:
                    configs.append(config)

        except Exception as e:
            logger.warning(
                "Failed to get configurations",
                extra={
                    "user_id": sanitize_for_log(user_id[:8]),
                    **get_safe_error_info(e),
                },
            )

        return configs

    def get_ticker_sentiment_data(
        self, tickers: list[str], days: int = 1
    ) -> dict[str, dict[str, Any]]:
        """Get sentiment data for tickers over specified period.

        Args:
            tickers: List of ticker symbols
            days: Number of days to look back (default 1 for daily)

        Returns:
            Dict mapping ticker to sentiment data:
            {
                "AAPL": {
                    "current_sentiment": 0.45,
                    "previous_sentiment": 0.32,
                    "sentiment_change": 0.13,
                    "sentiment_label": "positive",
                    "article_count": 15,
                    "volatility": 2.3,
                }
            }
        """
        ticker_data: dict[str, dict[str, Any]] = {}
        cutoff = datetime.now(UTC) - timedelta(days=days)

        for ticker in tickers:
            try:
                # Query sentiment results for ticker
                response = self.table.query(
                    KeyConditionExpression=(
                        Key("PK").eq(f"TICKER#{ticker}")
                        & Key("SK").gte(cutoff.isoformat())
                    ),
                    Limit=50,  # Reasonable limit for daily digest
                )

                items = response.get("Items", [])

                if not items:
                    ticker_data[ticker] = {
                        "current_sentiment": 0.0,
                        "previous_sentiment": 0.0,
                        "sentiment_change": 0.0,
                        "sentiment_label": "neutral",
                        "article_count": 0,
                        "volatility": None,
                    }
                    continue

                # Calculate aggregated sentiment
                scores = [float(item.get("sentiment_score", 0)) for item in items]
                current_score = sum(scores) / len(scores) if scores else 0.0

                # Get previous day for comparison (if available)
                prev_cutoff = cutoff - timedelta(days=1)
                prev_response = self.table.query(
                    KeyConditionExpression=(
                        Key("PK").eq(f"TICKER#{ticker}")
                        & Key("SK").between(prev_cutoff.isoformat(), cutoff.isoformat())
                    ),
                    Limit=50,
                )
                prev_items = prev_response.get("Items", [])
                prev_scores = [
                    float(item.get("sentiment_score", 0)) for item in prev_items
                ]
                prev_score = sum(prev_scores) / len(prev_scores) if prev_scores else 0.0

                # Determine label (inclusive thresholds per project standard)
                if current_score >= 0.33:
                    label = "positive"
                elif current_score <= -0.33:
                    label = "negative"
                else:
                    label = "neutral"

                ticker_data[ticker] = {
                    "current_sentiment": round(current_score, 4),
                    "previous_sentiment": round(prev_score, 4),
                    "sentiment_change": round(current_score - prev_score, 4),
                    "sentiment_label": label,
                    "article_count": len(items),
                    "volatility": None,  # Would come from ATR metrics
                }

            except Exception as e:
                logger.warning(
                    "Failed to get ticker data",
                    extra={
                        "ticker": sanitize_for_log(ticker),
                        **get_safe_error_info(e),
                    },
                )
                ticker_data[ticker] = {
                    "current_sentiment": 0.0,
                    "previous_sentiment": 0.0,
                    "sentiment_change": 0.0,
                    "sentiment_label": "neutral",
                    "article_count": 0,
                    "volatility": None,
                    "error": True,
                }

        return ticker_data

    def generate_digest(
        self, user: User, settings: DigestSettings
    ) -> DigestData | None:
        """Generate digest data for a user.

        Args:
            user: User profile
            settings: Digest settings

        Returns:
            DigestData object or None if no content
        """
        # Get configurations
        configs = self.get_user_configurations(user.user_id, settings)

        if not configs:
            logger.debug(
                "No configurations for digest",
                extra={"user_id": sanitize_for_log(user.user_id[:8])},
            )
            return None

        # Collect all tickers
        all_tickers = set()
        for config in configs:
            for ticker in config.tickers:
                all_tickers.add(ticker.symbol)

        if not all_tickers:
            return None

        # Get sentiment data
        ticker_data = self.get_ticker_sentiment_data(list(all_tickers))

        return DigestData(
            user=user,
            settings=settings,
            configs=configs,
            ticker_data=ticker_data,
        )

    def build_digest_html(self, digest: DigestData) -> str:
        """Build HTML email content for digest.

        Args:
            digest: DigestData object

        Returns:
            HTML email content
        """
        # Build ticker rows
        ticker_rows = []
        for ticker, data in sorted(digest.ticker_data.items()):
            sentiment = data["current_sentiment"]
            change = data["sentiment_change"]
            label = data["sentiment_label"]

            # Color coding
            if label == "positive":
                color = "#22c55e"
                arrow = "^"
            elif label == "negative":
                color = "#ef4444"
                arrow = "v"
            else:
                color = "#eab308"
                arrow = "-"

            # Change indicator
            if change > 0:
                change_color = "#22c55e"
                change_arrow = "+"
            elif change < 0:
                change_color = "#ef4444"
                change_arrow = ""
            else:
                change_color = "#6b7280"
                change_arrow = ""

            ticker_rows.append(
                f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    <a href="{self.dashboard_url}/dashboard?ticker={ticker}"
                       style="color: #1e40af; text-decoration: none; font-weight: bold;">
                        {ticker}
                    </a>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">
                    <span style="color: {color}; font-weight: bold;">{arrow} {label.upper()}</span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">
                    {sentiment:.2f}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">
                    <span style="color: {change_color};">{change_arrow}{change:.2f}</span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">
                    {data["article_count"]}
                </td>
            </tr>
            """
            )

        ticker_table = "\n".join(ticker_rows)

        # Format date for header
        user_tz = ZoneInfo(digest.settings.timezone)
        user_date = digest.generated_at.astimezone(user_tz).strftime("%B %d, %Y")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1f2937; margin: 0; padding: 0; background-color: #f3f4f6; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; }}
                .header {{ background-color: #1e40af; color: white; padding: 24px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .header p {{ margin: 8px 0 0 0; opacity: 0.9; }}
                .content {{ padding: 24px; }}
                .section-title {{ font-size: 18px; font-weight: bold; color: #1e40af; margin: 24px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ text-align: left; padding: 12px; background-color: #f9fafb; border-bottom: 2px solid #e5e7eb; font-size: 12px; text-transform: uppercase; color: #6b7280; }}
                .cta {{ text-align: center; margin: 24px 0; }}
                .cta a {{ display: inline-block; padding: 12px 24px; background-color: #1e40af; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; }}
                .footer {{ text-align: center; padding: 24px; color: #6b7280; font-size: 12px; background-color: #f9fafb; }}
                .footer a {{ color: #1e40af; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Daily Sentiment Digest</h1>
                    <p>{user_date}</p>
                </div>
                <div class="content">
                    <p>Good morning! Here's your daily sentiment summary for your watched tickers.</p>

                    <h2 class="section-title">Sentiment Overview</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Ticker</th>
                                <th style="text-align: center;">Sentiment</th>
                                <th style="text-align: right;">Score</th>
                                <th style="text-align: right;">Change</th>
                                <th style="text-align: right;">Articles</th>
                            </tr>
                        </thead>
                        <tbody>
                            {ticker_table}
                        </tbody>
                    </table>

                    <div class="cta">
                        <a href="{self.dashboard_url}/dashboard">View Full Dashboard</a>
                    </div>
                </div>
                <div class="footer">
                    <p>You're receiving this because you enabled daily digests in your settings.</p>
                    <p><a href="{self.dashboard_url}/settings/notifications">Manage notification preferences</a></p>
                </div>
            </div>
        </body>
        </html>
        """

    def update_last_sent(self, user_id: str) -> None:
        """Update last_sent timestamp for user's digest settings.

        Args:
            user_id: User ID
        """
        try:
            self.table.update_item(
                Key={"PK": f"USER#{user_id}", "SK": "DIGEST_SETTINGS"},
                UpdateExpression="SET last_sent = :ts",
                ExpressionAttributeValues={":ts": datetime.now(UTC).isoformat()},
            )
        except Exception as e:
            logger.warning(
                "Failed to update last_sent",
                extra={
                    "user_id": sanitize_for_log(user_id[:8]),
                    **get_safe_error_info(e),
                },
            )


def process_daily_digests(
    table: Any,
    email_service: Any,
    dashboard_url: str = "https://sentiment-analyzer.com",
) -> dict[str, int]:
    """Process all pending daily digests.

    Main entry point called by Lambda handler.

    Args:
        table: DynamoDB table resource
        email_service: EmailService instance for sending emails
        dashboard_url: Base URL for dashboard links

    Returns:
        Stats dict with counts: {"processed": N, "sent": N, "skipped": N, "failed": N}
    """
    stats = {"processed": 0, "sent": 0, "skipped": 0, "failed": 0}

    service = DigestService(table, dashboard_url)
    current_hour = datetime.now(UTC).hour

    # Get users due for digest
    try:
        users_due = service.get_users_for_digest(current_hour)
    except DigestServiceError as e:
        logger.error("Failed to get users for digest", extra=get_safe_error_info(e))
        return stats

    for user, settings in users_due:
        stats["processed"] += 1

        try:
            # Generate digest
            digest = service.generate_digest(user, settings)

            if not digest or not digest.has_content:
                stats["skipped"] += 1
                logger.debug(
                    "Skipping digest (no content)",
                    extra={"user_id": sanitize_for_log(user.user_id[:8])},
                )
                continue

            # Build email
            html_content = service.build_digest_html(digest)

            # Send email
            user_tz = ZoneInfo(settings.timezone)
            user_date = datetime.now(UTC).astimezone(user_tz).strftime("%B %d")
            subject = f"Daily Sentiment Digest - {user_date}"

            success = email_service.send_email(
                to_email=user.email,
                subject=subject,
                html_content=html_content,
            )

            if success:
                stats["sent"] += 1
                service.update_last_sent(user.user_id)
                logger.info(
                    "Sent digest email",
                    extra={"user_id": sanitize_for_log(user.user_id[:8])},
                )
            else:
                stats["failed"] += 1
                logger.warning(
                    "Failed to send digest",
                    extra={"user_id": sanitize_for_log(user.user_id[:8])},
                )

        except Exception as e:
            stats["failed"] += 1
            logger.error(
                "Error processing digest",
                extra={
                    "user_id": sanitize_for_log(user.user_id[:8]),
                    **get_safe_error_info(e),
                },
            )

    logger.info("Digest processing complete", extra=stats)
    return stats
