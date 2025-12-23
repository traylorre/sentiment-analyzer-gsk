# Data Model: OHLC Resolution Selector (Feature 1035)

**Date**: 2025-12-23
**Feature Branch**: `1035-ohlc-resolution-selector`

## Entities

### OHLCResolution (New Entity)

Represents the time duration each OHLC candlestick represents.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| value | string (enum) | Resolution identifier | One of: "1", "5", "15", "30", "60", "D" |
| label | string | Display label | "1 min", "5 min", "15 min", "30 min", "1 hour", "Daily" |
| finnhub_value | string | Finnhub API parameter | Maps to Finnhub resolution values |
| max_days | integer | Maximum time range allowed | Prevents excessive data fetching |

**Enum Values**:
```
ONE_MINUTE = "1"     # max_days: 7
FIVE_MINUTES = "5"   # max_days: 30
FIFTEEN_MINUTES = "15" # max_days: 90
THIRTY_MINUTES = "30"  # max_days: 90
ONE_HOUR = "60"      # max_days: 180
DAILY = "D"          # max_days: 365
```

### PriceCandle (Existing, Unchanged)

| Field | Type | Description |
|-------|------|-------------|
| date | datetime | Candle timestamp (bucket start) |
| open | decimal | Opening price |
| high | decimal | Highest price |
| low | decimal | Lowest price |
| close | decimal | Closing price |
| volume | integer (optional) | Trading volume |

### OHLCResponse (Existing, Extended)

| Field | Type | Description | Change |
|-------|------|-------------|--------|
| ticker | string | Stock symbol | Unchanged |
| candles | PriceCandle[] | Array of candles | Unchanged |
| time_range | string | Time range used | Unchanged |
| start_date | date | Start of data | Unchanged |
| end_date | date | End of data | Unchanged |
| count | integer | Number of candles | Unchanged |
| source | string | Data source | Unchanged |
| cache_expires_at | datetime | Cache expiry | Unchanged |
| **resolution** | string | **Resolution used** | **NEW** |

### UserPreference (Session Storage)

Stored in browser sessionStorage.

| Field | Type | Description |
|-------|------|-------------|
| preferred_resolution | string | Last selected resolution value |

**Storage Key**: `ohlc_preferred_resolution`

## State Transitions

### Resolution Selection Flow

```
┌─────────────┐   user clicks   ┌─────────────────┐   data loaded   ┌──────────────┐
│   Idle      │ ───────────────►│    Loading      │ ───────────────►│   Display    │
│ (current    │                 │  (new res)      │                 │ (new candles)│
│  resolution)│                 │                 │                 │              │
└─────────────┘                 └─────────────────┘                 └──────────────┘
       ▲                               │                                   │
       │                               │ fetch error                       │
       │                               ▼                                   │
       │                        ┌─────────────┐                            │
       └────────────────────────│   Error     │◄───────────────────────────┘
           retry/fallback       │  (fallback  │     resolution unavailable
                                │   to daily) │
                                └─────────────┘
```

## Validation Rules

### Resolution Validation
1. Resolution must be one of the defined enum values
2. Unknown resolution → reject with 400 Bad Request
3. Empty resolution → default to DAILY ("D")

### Time Range + Resolution Validation
1. If selected time range exceeds max_days for resolution:
   - Automatically limit to max_days
   - Notify user of the adjustment
2. If start_date + max_days < end_date:
   - Truncate to (end_date - max_days, end_date)

### Ticker + Resolution Availability
1. If Finnhub returns "no_data" for intraday:
   - Fallback to daily resolution
   - Display message: "Intraday data unavailable for {ticker}, showing daily"

## Relationships

```
┌──────────────────┐      fetches      ┌──────────────────┐
│                  │ ─────────────────►│                  │
│   User Session   │                   │   OHLC Endpoint  │
│ (preference)     │◄───────────────── │  (resolution)    │
│                  │      returns      │                  │
└──────────────────┘                   └──────────────────┘
                                              │
                                              │ queries
                                              ▼
                                       ┌──────────────────┐
                                       │   Finnhub API    │
                                       │ (with resolution)│
                                       └──────────────────┘
```
