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
    // API Configuration
    // Empty string means same origin (Lambda Function URL serves both static and API)
    API_BASE_URL: '',

    // Endpoints (API v2)
    ENDPOINTS: {
        SENTIMENT: '/api/v2/sentiment',
        TRENDS: '/api/v2/trends',
        ARTICLES: '/api/v2/articles',
        METRICS: '/api/v2/metrics',
        STREAM: '/api/v2/stream'  // SSE endpoint (may not be implemented)
    },

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
    }
};

// Freeze config to prevent accidental modifications
Object.freeze(CONFIG);
Object.freeze(CONFIG.ENDPOINTS);
Object.freeze(CONFIG.COLORS);
Object.freeze(CONFIG.COLORS_BG);
Object.freeze(CONFIG.DATE_FORMAT);
Object.freeze(CONFIG.SENTIMENT_LABELS);
