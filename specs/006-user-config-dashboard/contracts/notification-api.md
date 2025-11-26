# Notification & Alerts API Contract

**Feature**: 006-user-config-dashboard | **Version**: 1.0
**Base URL**: `https://{lambda-url}.lambda-url.{region}.on.aws` or `https://api.{domain}/v2`

## Overview

Alert system allows authenticated users to:
- Set sentiment threshold alerts (e.g., "alert when AAPL sentiment < -0.3")
- Set volatility threshold alerts (e.g., "alert when TSLA ATR > 3%")
- Receive email notifications via SendGrid
- View notification history

---

## Alert Rule Endpoints

### List Alert Rules

```http
GET /api/v2/alerts
Authorization: Bearer {access_token}
```

**Query Parameters**:
- `config_id`: Filter by configuration (optional)
- `ticker`: Filter by ticker (optional)
- `enabled`: Filter by enabled status (optional)

**Response** (200 OK):
```json
{
  "alerts": [
    {
      "alert_id": "uuid",
      "config_id": "uuid",
      "ticker": "AAPL",
      "alert_type": "sentiment_threshold",
      "threshold_value": -0.3,
      "threshold_direction": "below",
      "is_enabled": true,
      "last_triggered_at": "2025-11-25T14:30:00Z",
      "trigger_count": 3,
      "created_at": "2025-11-20T10:00:00Z"
    },
    {
      "alert_id": "uuid",
      "config_id": "uuid",
      "ticker": "TSLA",
      "alert_type": "volatility_threshold",
      "threshold_value": 5.0,
      "threshold_direction": "above",
      "is_enabled": true,
      "last_triggered_at": null,
      "trigger_count": 0,
      "created_at": "2025-11-22T10:00:00Z"
    }
  ],
  "total": 2,
  "daily_email_quota": {
    "used": 3,
    "limit": 10,
    "resets_at": "2025-11-27T00:00:00Z"
  }
}
```

### Create Alert Rule

```http
POST /api/v2/alerts
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "config_id": "uuid",
  "ticker": "NVDA",
  "alert_type": "sentiment_threshold",
  "threshold_value": -0.5,
  "threshold_direction": "below"
}
```

**Response** (201 Created):
```json
{
  "alert_id": "uuid",
  "config_id": "uuid",
  "ticker": "NVDA",
  "alert_type": "sentiment_threshold",
  "threshold_value": -0.5,
  "threshold_direction": "below",
  "is_enabled": true,
  "created_at": "2025-11-26T10:00:00Z"
}
```

**Validation Rules**:
- `alert_type`: Must be `sentiment_threshold` or `volatility_threshold`
- `threshold_value` for sentiment: -1.0 to 1.0
- `threshold_value` for volatility: 0.0 to 100.0 (percent)
- `threshold_direction`: `above` or `below`
- Maximum 10 alerts per configuration

**Errors**:
- `400 Bad Request`: Invalid threshold value or type
- `409 Conflict`: Maximum alerts (10) per config reached
- `403 Forbidden`: Anonymous users cannot create alerts

### Get Alert Rule

```http
GET /api/v2/alerts/{alert_id}
Authorization: Bearer {access_token}
```

**Response** (200 OK): Same as create response with additional fields

### Update Alert Rule

```http
PATCH /api/v2/alerts/{alert_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "threshold_value": -0.4,
  "is_enabled": false
}
```

**Response** (200 OK): Updated alert rule object

### Delete Alert Rule

```http
DELETE /api/v2/alerts/{alert_id}
Authorization: Bearer {access_token}
```

**Response** (204 No Content)

### Toggle Alert Status

```http
POST /api/v2/alerts/{alert_id}/toggle
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "alert_id": "uuid",
  "is_enabled": false,
  "message": "Alert disabled"
}
```

---

## Notification History Endpoints

### List Notifications

```http
GET /api/v2/notifications
Authorization: Bearer {access_token}
```

**Query Parameters**:
- `status`: Filter by status (`sent`, `failed`, `pending`)
- `alert_id`: Filter by alert rule
- `limit`: Max results (default: 20, max: 100)
- `offset`: Pagination offset

**Response** (200 OK):
```json
{
  "notifications": [
    {
      "notification_id": "uuid",
      "alert_id": "uuid",
      "ticker": "AAPL",
      "alert_type": "sentiment_threshold",
      "triggered_value": -0.42,
      "threshold_value": -0.3,
      "subject": "Alert: AAPL sentiment dropped below -0.3",
      "sent_at": "2025-11-25T14:32:00Z",
      "status": "sent",
      "deep_link": "https://app.domain/dashboard/config/uuid?highlight=AAPL"
    }
  ],
  "total": 15,
  "limit": 20,
  "offset": 0
}
```

### Get Notification Detail

```http
GET /api/v2/notifications/{notification_id}
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "notification_id": "uuid",
  "alert_id": "uuid",
  "ticker": "AAPL",
  "alert_type": "sentiment_threshold",
  "triggered_value": -0.42,
  "threshold_value": -0.3,
  "threshold_direction": "below",
  "subject": "Alert: AAPL sentiment dropped below -0.3",
  "body_preview": "The sentiment score for AAPL has dropped to -0.42...",
  "sent_at": "2025-11-25T14:32:00Z",
  "status": "sent",
  "email": "user@example.com",
  "deep_link": "https://app.domain/dashboard/config/uuid?highlight=AAPL",
  "tracking": {
    "opened_at": "2025-11-25T14:45:00Z",
    "clicked_at": "2025-11-25T14:46:00Z"
  }
}
```

---

## Notification Preferences

### Get Notification Preferences

```http
GET /api/v2/notifications/preferences
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "email_notifications_enabled": true,
  "daily_digest_enabled": false,
  "digest_time": "09:00",
  "timezone": "America/New_York",
  "email": "user@example.com",
  "email_verified": true
}
```

### Update Notification Preferences

```http
PATCH /api/v2/notifications/preferences
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "email_notifications_enabled": true,
  "daily_digest_enabled": true,
  "digest_time": "08:00"
}
```

**Response** (200 OK): Updated preferences object

### Disable All Notifications

```http
POST /api/v2/notifications/disable-all
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "status": "disabled",
  "alerts_disabled": 5,
  "message": "All notifications disabled"
}
```

---

## Unsubscribe (Email Link)

### Unsubscribe via Token

Called from unsubscribe link in notification emails.

```http
GET /api/v2/notifications/unsubscribe?token={unsubscribe_token}
```

**Response** (200 OK):
```json
{
  "status": "unsubscribed",
  "user_id": "uuid",
  "message": "You have been unsubscribed from notification emails"
}
```

**Response** (400 Bad Request) - Invalid Token:
```json
{
  "error": "invalid_token",
  "message": "Unsubscribe link is invalid or expired"
}
```

### Resubscribe

```http
POST /api/v2/notifications/resubscribe
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "status": "resubscribed",
  "message": "Email notifications re-enabled"
}
```

---

## Daily Digest Scheduling

### Get Digest Settings

```http
GET /api/v2/notifications/digest
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "enabled": true,
  "time": "09:00",
  "timezone": "America/New_York",
  "include_all_configs": true,
  "next_scheduled": "2025-11-27T14:00:00Z"
}
```

### Update Digest Settings

```http
PATCH /api/v2/notifications/digest
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "enabled": true,
  "time": "08:00",
  "timezone": "America/Los_Angeles",
  "include_all_configs": false,
  "config_ids": ["uuid-1"]
}
```

**Response** (200 OK):
```json
{
  "enabled": true,
  "time": "08:00",
  "timezone": "America/Los_Angeles",
  "include_all_configs": false,
  "config_ids": ["uuid-1"],
  "next_scheduled": "2025-11-27T16:00:00Z"
}
```

**Validation Rules**:
- `time`: 24-hour format HH:MM
- `timezone`: Valid IANA timezone string
- `config_ids`: Only required if `include_all_configs` is false

### Trigger Test Digest

For testing digest email format:

```http
POST /api/v2/notifications/digest/test
Authorization: Bearer {access_token}
```

**Response** (202 Accepted):
```json
{
  "status": "test_queued",
  "message": "Test digest email will be sent within 1 minute"
}
```

---

## Alert Evaluation (Internal)

### Evaluate Alerts (Lambda-to-Lambda)

Internal endpoint called by analysis Lambda after sentiment/volatility updates.

```http
POST /api/internal/alerts/evaluate
X-Internal-Auth: {internal_api_key}
Content-Type: application/json

{
  "ticker": "AAPL",
  "updates": {
    "sentiment": {
      "score": -0.42,
      "source": "tiingo",
      "timestamp": "2025-11-25T14:30:00Z"
    },
    "volatility": {
      "atr_percent": 2.8,
      "timestamp": "2025-11-25T14:30:00Z"
    }
  }
}
```

**Response** (200 OK):
```json
{
  "evaluated": 12,
  "triggered": 2,
  "notifications_queued": 2,
  "details": [
    {
      "alert_id": "uuid",
      "user_id": "uuid",
      "triggered": true,
      "current_value": -0.42,
      "threshold": -0.3,
      "notification_id": "uuid"
    }
  ]
}
```

---

## Email Templates

### Sentiment Alert Email

```html
Subject: Alert: {TICKER} sentiment {dropped below|rose above} {THRESHOLD}

The sentiment score for {TICKER} has {dropped to|risen to} {CURRENT_VALUE}.

Alert Details:
- Ticker: {TICKER}
- Current Sentiment: {CURRENT_VALUE} ({LABEL})
- Your Threshold: {THRESHOLD_DIRECTION} {THRESHOLD}
- Source: {SOURCE}
- Time: {TIMESTAMP}

View on Dashboard: {DEEP_LINK}

---
You're receiving this because you set up an alert for {TICKER}.
Unsubscribe: {UNSUBSCRIBE_LINK}
```

### Volatility Alert Email

```html
Subject: Alert: {TICKER} volatility {dropped below|exceeded} {THRESHOLD}%

The ATR volatility for {TICKER} has {dropped to|risen to} {CURRENT_VALUE}%.

Alert Details:
- Ticker: {TICKER}
- Current ATR: {CURRENT_VALUE}% ({TREND_ARROW})
- Your Threshold: {THRESHOLD_DIRECTION} {THRESHOLD}%
- Period: {ATR_PERIOD} days
- Time: {TIMESTAMP}

View on Dashboard: {DEEP_LINK}

---
You're receiving this because you set up an alert for {TICKER}.
Unsubscribe: {UNSUBSCRIBE_LINK}
```

### Daily Digest Email

```html
Subject: Daily Sentiment Digest - {DATE}

Here's your daily summary for your tracked tickers:

Configuration: {CONFIG_NAME}
---
{TICKER_1}: Sentiment {SCORE_1} ({LABEL_1}) | ATR {ATR_1}% {TREND_1}
{TICKER_2}: Sentiment {SCORE_2} ({LABEL_2}) | ATR {ATR_2}% {TREND_2}
...

Alerts Triggered Today: {ALERT_COUNT}
{ALERT_SUMMARY}

View Full Dashboard: {DASHBOARD_LINK}

---
Unsubscribe from daily digest: {UNSUBSCRIBE_LINK}
```

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /alerts` | 20 | per hour per user |
| `GET /notifications` | 100 | per minute per user |
| Internal evaluate | 1000 | per minute |

**Daily Email Limits**:
- 10 notification emails per user per day
- 100 total emails per day (SendGrid free tier)
- 50% quota alert at 50 emails/day

---

## Email Quota Monitoring (Internal)

### Get Quota Status

Internal endpoint for monitoring SendGrid quota usage.

```http
GET /api/internal/email-quota
X-Internal-Auth: {internal_api_key}
```

**Response** (200 OK):
```json
{
  "daily_limit": 100,
  "used_today": 47,
  "remaining": 53,
  "percent_used": 47.0,
  "reset_at": "2025-11-27T00:00:00Z",
  "alert_threshold": 50,
  "alert_triggered": false,
  "last_email_sent_at": "2025-11-26T15:30:00Z",
  "top_users": [
    {"user_id": "uuid-1", "count": 8},
    {"user_id": "uuid-2", "count": 6}
  ]
}
```

**Response** (200 OK) - Alert Triggered:
```json
{
  "daily_limit": 100,
  "used_today": 52,
  "remaining": 48,
  "percent_used": 52.0,
  "reset_at": "2025-11-27T00:00:00Z",
  "alert_threshold": 50,
  "alert_triggered": true,
  "alert_triggered_at": "2025-11-26T14:00:00Z",
  "alert_sent_to": ["admin@example.com"]
}
```

### Quota Alert CloudWatch Alarm

The system automatically creates a CloudWatch alarm for email quota:

```hcl
# Terraform config
resource "aws_cloudwatch_metric_alarm" "sendgrid_quota_alert" {
  alarm_name          = "${var.environment}-sendgrid-quota-50pct"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EmailsSentToday"
  namespace           = "SentimentAnalyzer/Notifications"
  period              = 300
  statistic           = "Maximum"
  threshold           = 50
  alarm_description   = "SendGrid daily quota exceeded 50%"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
```

### Quota Exceeded Behavior

When daily quota (100 emails) is exhausted:

1. **Alert emails** continue to queue (processed next day)
2. **Magic link emails** are prioritized (auth-critical)
3. **Digest emails** are skipped for the day
4. **Users see in-app banner**: "Email quota reached. Alerts will resume tomorrow."

```json
// API response when quota exceeded
{
  "error": {
    "code": "EMAIL_QUOTA_EXCEEDED",
    "message": "Daily email limit reached. Your alert has been queued for tomorrow.",
    "details": {
      "quota_resets_at": "2025-11-27T00:00:00Z",
      "queued_alerts": 3
    }
  }
}
```

---

## Error Responses

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `ALERT_LIMIT_EXCEEDED` | 409 | Max 10 alerts per config |
| `EMAIL_QUOTA_EXCEEDED` | 429 | Daily email limit (10) reached |
| `ANONYMOUS_NOT_ALLOWED` | 403 | Alerts require authentication |
| `INVALID_THRESHOLD` | 400 | Threshold value out of range |
| `TICKER_NOT_IN_CONFIG` | 400 | Ticker not in referenced config |
