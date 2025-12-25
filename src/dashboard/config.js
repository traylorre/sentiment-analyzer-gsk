/**
 * Dashboard Configuration
 * =======================
 *
 * For On-Call Engineers:
 *     If dashboard can't connect to API:
 *     1. Check CONFIG.API_BASE_URL matches Lambda Function URL
 *     2. Verify CORS is enabled on Lambda
 *     3. Check browser console for connection errors
 *
 * For Developers:
 *     - API_BASE_URL: Set to empty string for same-origin requests
 *     - Colors match CSS custom properties for consistency
 *     - Intervals can be adjusted for polling frequency
 */

const CONFIG = {
    // Session Storage Key (Feature 1050)
    // Used to persist anonymous session UUID in localStorage
    SESSION_KEY: 'sentiment_dashboard_session',

    // API Configuration
    // Empty string means same origin (Lambda Function URL serves both static and API)
    API_BASE_URL: '',

    // SSE Configuration (Two-Lambda Architecture)
    // SSE stream comes from a separate Lambda with RESPONSE_STREAM invoke mode
    // Set this to the SSE Lambda Function URL in production
    // Empty string means same origin (for local development or single-Lambda fallback)
    SSE_BASE_URL: '',

    // Endpoints (API v2)
    ENDPOINTS: {
        AUTH_ANONYMOUS: '/api/v2/auth/anonymous',  // Feature 1050: Anonymous session creation
        SENTIMENT: '/api/v2/sentiment',
        TRENDS: '/api/v2/trends',
        ARTICLES: '/api/v2/articles',
        METRICS: '/api/v2/metrics',
        STREAM: '/api/v2/stream',  // SSE endpoint (served by SSE Lambda)
        TIMESERIES: '/api/v2/timeseries',  // Timeseries endpoint: append /{ticker}?resolution=5m
        OHLC: '/api/v2/tickers'  // Feature 1057: OHLC endpoint: append /{ticker}/ohlc?resolution=D
    },

    // Feature 1057: OHLC resolution configuration
    // Maps backend resolution values to display labels
    // Backend accepts: '1', '5', '15', '30', '60', 'D'
    OHLC_RESOLUTIONS: [
        { key: '1', label: '1m', description: '1 minute candles' },
        { key: '5', label: '5m', description: '5 minute candles' },
        { key: '15', label: '15m', description: '15 minute candles' },
        { key: '30', label: '30m', description: '30 minute candles' },
        { key: '60', label: '1h', description: '1 hour candles' },
        { key: 'D', label: 'Day', description: 'Daily candles' }
    ],

    // Default OHLC resolution
    DEFAULT_OHLC_RESOLUTION: 'D',

    // OHLC chart colors
    OHLC_COLORS: {
        bullish: '#22c55e',  // Green for price up
        bearish: '#ef4444',  // Red for price down
        wick: '#6b7280'      // Gray for candle wicks
    },

    // Resolution configuration for multi-resolution timeseries (Feature 1009)
    // Values sourced from src/lib/timeseries/models.py Resolution enum
    RESOLUTIONS: {
        '1m': {
            key: '1m',
            displayName: '1 min',
            durationSeconds: 60,
            ttlSeconds: 21600  // 6 hours
        },
        '5m': {
            key: '5m',
            displayName: '5 min',
            durationSeconds: 300,
            ttlSeconds: 43200  // 12 hours
        },
        '10m': {
            key: '10m',
            displayName: '10 min',
            durationSeconds: 600,
            ttlSeconds: 86400  // 24 hours
        },
        '1h': {
            key: '1h',
            displayName: '1 hour',
            durationSeconds: 3600,
            ttlSeconds: 604800  // 7 days
        },
        '3h': {
            key: '3h',
            displayName: '3 hours',
            durationSeconds: 10800,
            ttlSeconds: 1209600  // 14 days
        },
        '6h': {
            key: '6h',
            displayName: '6 hours',
            durationSeconds: 21600,
            ttlSeconds: 2592000  // 30 days
        },
        '12h': {
            key: '12h',
            displayName: '12 hours',
            durationSeconds: 43200,
            ttlSeconds: 5184000  // 60 days
        },
        '24h': {
            key: '24h',
            displayName: '24 hours',
            durationSeconds: 86400,
            ttlSeconds: 7776000  // 90 days
        }
    },

    // Resolution display order for UI selectors
    RESOLUTION_ORDER: ['1m', '5m', '10m', '1h', '3h', '6h', '12h', '24h'],

    // Default resolution (Feature 1009 FR-002)
    DEFAULT_RESOLUTION: '5m',

    // Polling interval for sentiment data (milliseconds)
    SENTIMENT_POLL_INTERVAL: 30000, // 30 seconds

    // Metrics polling interval (milliseconds) - used as fallback when SSE fails
    METRICS_POLL_INTERVAL: 30000, // 30 seconds

    // SSE connection settings
    SSE_MAX_RETRIES: 3,
    SSE_RECONNECT_DELAY: 1000, // 1 second (doubles with each retry)

    // Chart colors (must match CSS custom properties)
    COLORS: {
        positive: '#22c55e',
        neutral: '#6b7280',
        negative: '#ef4444',
        primary: '#3b82f6'
    },

    // Chart background colors (with transparency)
    COLORS_BG: {
        positive: 'rgba(34, 197, 94, 0.2)',
        neutral: 'rgba(107, 114, 128, 0.2)',
        negative: 'rgba(239, 68, 68, 0.2)'
    },

    // Maximum items to display in recent items table
    MAX_RECENT_ITEMS: 20,

    // Date/time formatting options
    DATE_FORMAT: {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    },

    // Sentiment labels for display
    SENTIMENT_LABELS: {
        positive: 'Positive',
        neutral: 'Neutral',
        negative: 'Negative'
    },

    // Feature 1021: Skeleton Loading UI timing constants
    SKELETON: {
        // Timeout before showing error state (FR-010)
        TIMEOUT_MS: 30000,  // 30 seconds

        // Transition duration for skeleton to content
        TRANSITION_MS: 300,

        // Debounce delay for rapid resolution switches (US2)
        DEBOUNCE_MS: 300
    }
};

// Freeze config to prevent accidental modifications
Object.freeze(CONFIG);
Object.freeze(CONFIG.ENDPOINTS);
Object.freeze(CONFIG.COLORS);
Object.freeze(CONFIG.COLORS_BG);
Object.freeze(CONFIG.DATE_FORMAT);
Object.freeze(CONFIG.SENTIMENT_LABELS);
Object.freeze(CONFIG.RESOLUTIONS);
Object.freeze(CONFIG.RESOLUTION_ORDER);
// Deep freeze each resolution object
Object.values(CONFIG.RESOLUTIONS).forEach(r => Object.freeze(r));
Object.freeze(CONFIG.SKELETON);
// Feature 1057: Freeze OHLC config
Object.freeze(CONFIG.OHLC_RESOLUTIONS);
CONFIG.OHLC_RESOLUTIONS.forEach(r => Object.freeze(r));
Object.freeze(CONFIG.OHLC_COLORS);
