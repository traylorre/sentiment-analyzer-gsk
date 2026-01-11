"""Stripe utility functions for webhook handling.

Feature: 1191 - Mid-Session Tier Upgrade
"""

import logging
import os

import stripe
from stripe.error import SignatureVerificationError

logger = logging.getLogger(__name__)


def _get_webhook_secret() -> str:
    """Get Stripe webhook secret from environment.

    Amendment 1.15 compliant - fail if missing, no fallback.
    Lazy-loaded to allow module import during testing.
    """
    return os.environ["STRIPE_WEBHOOK_SECRET"]


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
