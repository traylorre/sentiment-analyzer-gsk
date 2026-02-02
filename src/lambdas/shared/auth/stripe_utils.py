"""Stripe utility functions for webhook handling.

Feature: 1191 - Mid-Session Tier Upgrade
"""

import logging
import os

import stripe

# Stripe SDK v8+: SignatureVerificationError moved from stripe.error to stripe
from stripe import SignatureVerificationError

logger = logging.getLogger(__name__)


def _get_webhook_secret() -> str:
    """Get Stripe webhook secret from Secrets Manager.

    Amendment 1.15 compliant - fail if missing, no fallback.
    Uses ARN pattern consistent with other project secrets.
    Lazy-loaded to allow module import during testing.
    """
    secret_arn = os.environ.get("STRIPE_WEBHOOK_SECRET_ARN", "")
    if not secret_arn:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET_ARN environment variable not set")

    # Import here to avoid circular imports
    from src.lambdas.shared.secrets import get_secret

    secret_data = get_secret(secret_arn)

    # Handle both formats: {"webhook_secret": "..."} or plain string
    if isinstance(secret_data, dict):
        return secret_data.get(
            "webhook_secret", secret_data.get("STRIPE_WEBHOOK_SECRET", "")
        )
    return str(secret_data)


def verify_stripe_signature(payload: bytes, signature: str) -> stripe.Event:
    """Verify Stripe webhook signature and construct event.

    Args:
        payload: Raw request body bytes
        signature: Value of stripe-signature header

    Returns:
        Verified Stripe Event object

    Raises:
        SignatureVerificationError: If signature is invalid
        ValueError: If payload cannot be parsed
    """
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=_get_webhook_secret(),
        )
        logger.info(
            "stripe_signature_verified",
            extra={"event_id": event.id, "event_type": event.type},
        )
        return event
    except SignatureVerificationError as e:
        logger.warning(
            "stripe_signature_invalid",
            extra={"error": str(e)},
        )
        raise


def extract_user_id_from_subscription(
    subscription: stripe.Subscription | dict,
) -> str | None:
    """Extract user_id from Stripe subscription metadata.

    Args:
        subscription: Stripe Subscription object or dict

    Returns:
        user_id if found in metadata, None otherwise
    """
    metadata = subscription.get("metadata", {})
    user_id = metadata.get("user_id")
    if not user_id:
        # Handle both Stripe objects (.id) and dicts (["id"])
        sub_id = getattr(subscription, "id", None) or subscription.get("id", "unknown")
        logger.warning(
            "stripe_subscription_missing_user_id",
            extra={"subscription_id": sub_id},
        )
    return user_id


def extract_price_id_from_subscription(subscription: stripe.Subscription) -> str | None:
    """Extract price_id from Stripe subscription items.

    Args:
        subscription: Stripe Subscription object

    Returns:
        price_id of first item if found, None otherwise
    """
    items = subscription.get("items", {}).get("data", [])
    if items:
        return items[0].get("price", {}).get("id")
    return None
