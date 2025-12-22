/**
 * Sentiment Analyzer Dashboard Application
 * =========================================
 *
 * For On-Call Engineers:
 *     If dashboard is not updating:
 *     1. Check connection status indicator (top right)
 *     2. Open browser console (F12) for errors
 *     3. Verify API endpoints return 200 status
 *     4. Check if SSE stream is connected (Network tab)
 *
 *     Common issues:
 *     - "Disconnected" status: Lambda may be cold starting
 *     - Charts not rendering: Check Chart.js CDN is accessible
 *     - Empty table: Check DynamoDB has items
 *
 * For Developers:
 *     - Uses Server-Sent Events (SSE) for real-time updates
 *     - Falls back to polling if SSE fails
 *     - Chart.js instances are stored globally for updates
 *     - Uses `timestamp` field from DynamoDB (not ingested_at)
 */

// Application state
const state = {
    connected: false,
    sseRetries: 0,
    eventSource: null,
    pollInterval: null,
    charts: {
        sentiment: null,
        tag: null
    },
    metrics: {
        total: 0,
        positive: 0,
        neutral: 0,
        negative: 0,
        byTag: {}
    },
    recentItems: []
};

/**
 * Initialize the dashboard application
 */
async function initDashboard() {
    console.log('Initializing dashboard...');

    // Initialize charts
    initCharts();

    // Initialize timeseries module (Feature 1009)
    if (typeof timeseriesManager !== 'undefined') {
        try {
            await timeseriesManager.init();
            console.log('Timeseries module initialized');
        } catch (error) {
            console.error('Failed to initialize timeseries:', error);
        }
    }

    // Fetch initial metrics
    await fetchMetrics();

    // Connect to SSE stream
    connectSSE();

    console.log('Dashboard initialized');
}

/**
 * Initialize Chart.js charts
 */
function initCharts() {
    // Sentiment distribution pie chart
    const sentimentCtx = document.getElementById('sentiment-chart').getContext('2d');
    state.charts.sentiment = new Chart(sentimentCtx, {
        type: 'doughnut',
        data: {
            labels: ['Positive', 'Neutral', 'Negative'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: [
                    CONFIG.COLORS.positive,
                    CONFIG.COLORS.neutral,
                    CONFIG.COLORS.negative
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });

    // Tag distribution bar chart
    const tagCtx = document.getElementById('tag-chart').getContext('2d');
    state.charts.tag = new Chart(tagCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Items by Tag',
                data: [],
                backgroundColor: CONFIG.COLORS.primary,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

/**
 * Fetch metrics from API
 *
 * Feature 1011: Includes Authorization header when API key is configured.
 * API key is injected by server at render time (window.DASHBOARD_API_KEY).
 */
async function fetchMetrics() {
    try {
        // Build request options with optional Authorization header (Feature 1011)
        const options = {};
        if (CONFIG.API_KEY) {
            options.headers = {
                'Authorization': `Bearer ${CONFIG.API_KEY}`
            };
        }

        const response = await fetch(
            `${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.METRICS}`,
            options
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        updateMetrics(data);
        updateConnectionStatus(true);

    } catch (error) {
        console.error('Failed to fetch metrics:', error);
        updateConnectionStatus(false);
    }
}

/**
 * Update metrics display with new data
 */
function updateMetrics(data) {
    // Update state
    state.metrics = {
        total: data.total || 0,
        positive: data.positive || 0,
        neutral: data.neutral || 0,
        negative: data.negative || 0,
        byTag: data.by_tag || {}
    };

    // Update metric cards
    document.getElementById('total-items').textContent = state.metrics.total;
    document.getElementById('positive-count').textContent = state.metrics.positive;
    document.getElementById('neutral-count').textContent = state.metrics.neutral;
    document.getElementById('negative-count').textContent = state.metrics.negative;

    // Update percentages
    const total = state.metrics.total || 1; // Avoid division by zero
    document.getElementById('positive-pct').textContent =
        `${Math.round((state.metrics.positive / total) * 100)}%`;
    document.getElementById('neutral-pct').textContent =
        `${Math.round((state.metrics.neutral / total) * 100)}%`;
    document.getElementById('negative-pct').textContent =
        `${Math.round((state.metrics.negative / total) * 100)}%`;

    // Update sentiment chart
    state.charts.sentiment.data.datasets[0].data = [
        state.metrics.positive,
        state.metrics.neutral,
        state.metrics.negative
    ];
    state.charts.sentiment.update();

    // Update tag chart
    const tags = Object.keys(state.metrics.byTag);
    const tagCounts = Object.values(state.metrics.byTag);
    state.charts.tag.data.labels = tags;
    state.charts.tag.data.datasets[0].data = tagCounts;
    state.charts.tag.update();

    // Update ingestion stats
    if (data.rate_last_hour !== undefined) {
        document.getElementById('rate-last-hour').textContent = data.rate_last_hour;
    }
    if (data.rate_last_24h !== undefined) {
        document.getElementById('rate-last-24h').textContent = data.rate_last_24h;
    }

    // Update last updated timestamp
    document.getElementById('last-updated').textContent =
        new Date().toLocaleTimeString(undefined, CONFIG.DATE_FORMAT);

    // Update recent items if included
    if (data.recent_items) {
        updateRecentItems(data.recent_items);
    }
}

/**
 * Update recent items table
 */
function updateRecentItems(items) {
    const tbody = document.getElementById('items-tbody');
    const existingIds = new Set(state.recentItems.map(item => item.source_id));

    // Merge new items with existing ones
    items.forEach(item => {
        if (!existingIds.has(item.source_id)) {
            state.recentItems.unshift(item);
        }
    });

    // Limit to max items
    state.recentItems = state.recentItems.slice(0, CONFIG.MAX_RECENT_ITEMS);

    // Sort by timestamp descending
    state.recentItems.sort((a, b) => {
        const timeA = new Date(a.timestamp).getTime();
        const timeB = new Date(b.timestamp).getTime();
        return timeB - timeA;
    });

    // Render table
    tbody.innerHTML = state.recentItems.map((item, index) => {
        const isNew = index === 0 && items.some(i => i.source_id === item.source_id);
        const rowClass = isNew ? 'new-item' : '';

        const timestamp = new Date(item.timestamp).toLocaleTimeString(undefined, CONFIG.DATE_FORMAT);
        const sentiment = item.sentiment || 'pending';
        const score = item.score !== undefined ? item.score.toFixed(2) : '--';
        const title = escapeHtml(item.title || 'Untitled');
        const source = item.source || 'unknown';
        const tags = item.tags || [];

        return `
            <tr class="${rowClass}">
                <td>${timestamp}</td>
                <td>
                    <span class="sentiment-badge ${sentiment}">
                        ${CONFIG.SENTIMENT_LABELS[sentiment] || sentiment}
                    </span>
                </td>
                <td>${score}</td>
                <td title="${title}">${truncateText(title, 50)}</td>
                <td>${source}</td>
                <td>
                    <div class="tags">
                        ${tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Connect to Server-Sent Events stream
 *
 * Uses SSE_BASE_URL for the SSE Lambda (two-Lambda architecture).
 * Falls back to API_BASE_URL if SSE_BASE_URL is not configured.
 */
function connectSSE() {
    if (state.eventSource) {
        state.eventSource.close();
    }

    console.log('Connecting to SSE stream...');

    // Use SSE_BASE_URL if configured, otherwise fall back to API_BASE_URL
    const baseUrl = CONFIG.SSE_BASE_URL || CONFIG.API_BASE_URL;
    const streamUrl = `${baseUrl}${CONFIG.ENDPOINTS.STREAM}`;
    console.log('SSE stream URL:', streamUrl);
    state.eventSource = new EventSource(streamUrl);

    state.eventSource.onopen = () => {
        console.log('SSE connection established');
        state.sseRetries = 0;
        updateConnectionStatus(true);

        // Clear fallback polling if active
        if (state.pollInterval) {
            clearInterval(state.pollInterval);
            state.pollInterval = null;
        }
    };

    state.eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleSSEMessage(data);
        } catch (error) {
            console.error('Failed to parse SSE message:', error);
        }
    };

    state.eventSource.addEventListener('metrics', (event) => {
        try {
            const data = JSON.parse(event.data);
            updateMetrics(data);
        } catch (error) {
            console.error('Failed to parse metrics event:', error);
        }
    });

    state.eventSource.addEventListener('new_item', (event) => {
        try {
            const item = JSON.parse(event.data);
            updateRecentItems([item]);
        } catch (error) {
            console.error('Failed to parse new_item event:', error);
        }
    });

    state.eventSource.onerror = (error) => {
        console.error('SSE connection error:', error);
        updateConnectionStatus(false);

        state.eventSource.close();
        state.eventSource = null;

        // Retry connection with exponential backoff
        if (state.sseRetries < CONFIG.SSE_MAX_RETRIES) {
            state.sseRetries++;
            const delay = CONFIG.SSE_RECONNECT_DELAY * Math.pow(2, state.sseRetries - 1);
            console.log(`Retrying SSE connection in ${delay}ms (attempt ${state.sseRetries}/${CONFIG.SSE_MAX_RETRIES})`);
            setTimeout(connectSSE, delay);
        } else {
            console.log('Max SSE retries reached, falling back to polling');
            startPolling();
        }
    };
}

/**
 * Handle generic SSE message
 */
function handleSSEMessage(data) {
    if (data.type === 'metrics') {
        updateMetrics(data);
    } else if (data.type === 'new_item') {
        updateRecentItems([data.item]);
    } else if (data.type === 'heartbeat') {
        // Keep connection alive
        updateConnectionStatus(true);
    }
}

/**
 * Start polling as fallback when SSE fails
 */
function startPolling() {
    if (state.pollInterval) {
        return; // Already polling
    }

    console.log('Starting polling fallback');

    state.pollInterval = setInterval(async () => {
        await fetchMetrics();
    }, CONFIG.METRICS_POLL_INTERVAL);
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(connected) {
    state.connected = connected;

    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');

    if (connected) {
        indicator.classList.remove('disconnected');
        indicator.classList.add('connected');
        text.textContent = 'Connected';
    } else {
        indicator.classList.remove('connected');
        indicator.classList.add('disconnected');
        text.textContent = 'Disconnected';
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Truncate text with ellipsis
 */
function truncateText(text, maxLength) {
    if (text.length <= maxLength) {
        return text;
    }
    return text.substring(0, maxLength - 3) + '...';
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initDashboard);

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (state.eventSource) {
        state.eventSource.close();
    }
    if (state.pollInterval) {
        clearInterval(state.pollInterval);
    }
    // Cleanup timeseries module (Feature 1009)
    if (typeof timeseriesManager !== 'undefined') {
        timeseriesManager.destroy();
    }
});
