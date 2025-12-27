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

// Feature 1050: Session user ID for X-User-ID header
let sessionUserId = null;

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
    recentItems: [],
    // Phase 7: Connectivity Resilience (US5) state
    connectionMode: 'connecting',  // 'streaming' | 'polling' | 'offline' | 'connecting'
    isOnline: navigator.onLine,
    reconnectTimer: null
};

/**
 * Feature 1021: Skeleton Loading UI State
 * ========================================
 * FR-011: Never show loading spinners, skeleton UI only
 * SC-009: Zero loading spinners visible
 */
const skeletonState = {
    chart: false,
    tickerList: false,
    resolution: false,
    metrics: false,
    table: false
};

// Skeleton timeout handles (FR-010: 30s timeout)
const skeletonTimeouts = {};

/**
 * Feature 1050: Validate UUID4 format
 *
 * @param {string} str - String to validate
 * @returns {boolean} - True if valid UUID4
 */
function isValidUUID(str) {
    if (!str || typeof str !== 'string') return false;
    const uuid4Regex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuid4Regex.test(str);
}

/**
 * Feature 1050: Initialize anonymous session (FR-001, FR-002, FR-004)
 *
 * Creates or restores an anonymous session for API authentication.
 * Session UUID is stored in localStorage and sent via X-User-ID header.
 *
 * @returns {Promise<boolean>} - True if session initialized successfully
 */
async function initSession() {
    console.log('Initializing session...');

    // FR-004: Check localStorage for existing valid session
    try {
        const storedUserId = localStorage.getItem(CONFIG.SESSION_KEY);
        if (storedUserId && isValidUUID(storedUserId)) {
            console.log('Restored session from localStorage:', storedUserId.substring(0, 8) + '...');
            sessionUserId = storedUserId;
            return true;
        }
    } catch (e) {
        // localStorage may not be available (private browsing, etc.)
        console.warn('localStorage not available:', e.message);
    }

    // FR-001: Create new anonymous session
    try {
        const response = await fetch(
            `${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.AUTH_ANONYMOUS}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            }
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        const userId = data.userId || data.user_id;

        if (!userId || !isValidUUID(userId)) {
            throw new Error('Invalid user ID received from server');
        }

        sessionUserId = userId;
        console.log('Created new anonymous session:', userId.substring(0, 8) + '...');

        // FR-002: Store in localStorage for persistence
        try {
            localStorage.setItem(CONFIG.SESSION_KEY, userId);
        } catch (e) {
            console.warn('Could not persist session to localStorage:', e.message);
        }

        return true;

    } catch (error) {
        console.error('Failed to initialize session:', error);
        return false;
    }
}

/**
 * Show skeleton for a component (T003)
 *
 * @param {string} component - Component name (chart, tickerList, resolution, metrics, table)
 */
function showSkeleton(component) {
    skeletonState[component] = true;
    const overlay = document.querySelector(`[data-skeleton="${component}"]`);
    if (overlay) {
        overlay.classList.remove('hidden');
        // Set aria-busy on parent container (RQ-4: Accessibility)
        const container = overlay.parentElement;
        if (container) {
            container.setAttribute('aria-busy', 'true');
        }
    }
}

/**
 * Hide skeleton for a component with smooth transition (T003)
 *
 * @param {string} component - Component name
 */
function hideSkeleton(component) {
    skeletonState[component] = false;
    const overlay = document.querySelector(`[data-skeleton="${component}"]`);
    if (overlay) {
        overlay.classList.add('hidden');
        // Clear aria-busy on parent container
        const container = overlay.parentElement;
        if (container) {
            container.setAttribute('aria-busy', 'false');
        }
    }
    // Clear any pending timeout
    if (skeletonTimeouts[component]) {
        clearTimeout(skeletonTimeouts[component]);
        delete skeletonTimeouts[component];
    }
}

/**
 * Start skeleton with timeout (T021: FR-010 - 30s timeout)
 *
 * @param {string} component - Component name
 * @param {number} timeoutMs - Timeout in milliseconds (default: CONFIG.SKELETON.TIMEOUT_MS)
 */
function startSkeletonWithTimeout(component, timeoutMs = null) {
    const timeout = timeoutMs || (CONFIG.SKELETON ? CONFIG.SKELETON.TIMEOUT_MS : 30000);
    showSkeleton(component);

    // Clear any existing timeout
    if (skeletonTimeouts[component]) {
        clearTimeout(skeletonTimeouts[component]);
    }

    // Set timeout to show error state
    skeletonTimeouts[component] = setTimeout(() => {
        showSkeletonError(component, 'Request timed out. Please refresh the page.');
    }, timeout);
}

/**
 * Cancel skeleton and mark as success (T008: Cancel pending when data arrives)
 *
 * @param {string} component - Component name
 */
function skeletonSuccess(component) {
    if (skeletonTimeouts[component]) {
        clearTimeout(skeletonTimeouts[component]);
        delete skeletonTimeouts[component];
    }
    hideSkeleton(component);
}

/**
 * Show error state after skeleton timeout (T021, T022)
 *
 * @param {string} component - Component name
 * @param {string} message - Error message to display
 */
function showSkeletonError(component, message) {
    skeletonState[component] = false;
    const overlay = document.querySelector(`[data-skeleton="${component}"]`);
    if (overlay) {
        overlay.innerHTML = `
            <div class="skeleton-error">
                <div class="skeleton-error-icon">⚠️</div>
                <div class="skeleton-error-message">${message}</div>
            </div>
        `;
        overlay.classList.remove('hidden');
    }
}

/**
 * Initialize the dashboard application
 */
async function initDashboard() {
    console.log('Initializing dashboard...');

    // Feature 1021 (T010): Show skeletons immediately on page load
    // SC-002: Skeleton appears within 100ms of navigation
    initSkeletons();

    // Feature 1050 (FR-006): Initialize session before any API calls
    const sessionReady = await initSession();
    if (!sessionReady) {
        console.error('Session initialization failed - dashboard cannot load');
        showSkeletonError('metrics', 'Failed to initialize session. Please refresh the page.');
        showSkeletonError('chart', 'Session initialization failed');
        return;
    }

    // Initialize charts
    initCharts();

    // Phase 7: Set up offline/online event listeners [CS-007]
    setupConnectivityListeners();

    // Initialize timeseries module (Feature 1009)
    if (typeof timeseriesManager !== 'undefined') {
        try {
            await timeseriesManager.init();
            console.log('Timeseries module initialized');
            // Hide resolution skeleton once timeseries is ready
            skeletonSuccess('resolution');
        } catch (error) {
            console.error('Failed to initialize timeseries:', error);
            showSkeletonError('resolution', 'Failed to load resolution selector');
        }
    } else {
        // No timeseries module, hide skeleton
        hideSkeleton('resolution');
    }

    // Feature 1057: Initialize OHLC chart
    if (typeof initOHLCChart === 'function') {
        try {
            await initOHLCChart('AAPL');
            console.log('OHLC chart initialized');
        } catch (error) {
            console.error('Failed to initialize OHLC chart:', error);
            showSkeletonError('ohlcChart', 'Failed to load price chart');
        }
    }

    // Feature 1064: Initialize Unified Resolution Selector
    if (typeof initUnifiedResolution === 'function') {
        try {
            initUnifiedResolution({
                containerId: 'unified-resolution-selector',
                onOhlcChange: async (resolution, isFallback) => {
                    if (typeof setOHLCResolution === 'function') {
                        await setOHLCResolution(resolution, isFallback);
                    }
                },
                onSentimentChange: async (resolution, isFallback) => {
                    if (typeof setSentimentResolution === 'function') {
                        await setSentimentResolution(resolution, isFallback);
                    }
                }
            });
            console.log('Unified resolution selector initialized');

            // Bind ticker input to update both charts
            const tickerInput = document.getElementById('ticker-input');
            if (tickerInput) {
                tickerInput.addEventListener('keydown', async (e) => {
                    if (e.key === 'Enter') {
                        const ticker = tickerInput.value.toUpperCase().trim();
                        if (ticker) {
                            // Update both charts
                            if (typeof updateOHLCTicker === 'function') {
                                await updateOHLCTicker(ticker);
                            }
                            if (typeof getTimeseriesManager === 'function') {
                                const tsManager = getTimeseriesManager();
                                if (tsManager && typeof tsManager.switchTicker === 'function') {
                                    await tsManager.switchTicker(ticker);
                                }
                            }
                        }
                    }
                });
            }
        } catch (error) {
            console.error('Failed to initialize unified resolution selector:', error);
        }
    }

    // Fetch initial metrics
    await fetchMetrics();

    // Connect to SSE stream
    connectSSE();

    console.log('Dashboard initialized');
}

/**
 * Feature 1021 (T010): Initialize all skeletons on page load
 *
 * FR-001: Display skeleton for chart area immediately on page load
 * FR-002: Display skeleton for ticker list during initial load
 * FR-003: Display skeleton for resolution selector during initial load
 */
function initSkeletons() {
    // Show all skeletons with timeout protection (FR-010)
    startSkeletonWithTimeout('metrics');
    startSkeletonWithTimeout('resolution');
    startSkeletonWithTimeout('chart');
    startSkeletonWithTimeout('sentimentChart');
    startSkeletonWithTimeout('tagChart');
    startSkeletonWithTimeout('table');
    console.log('Skeleton loading UI initialized');
}

/**
 * Phase 7 (T059): Set up network connectivity listeners
 *
 * Canonical Source: [CS-007] MDN Server-Sent Events
 * FR-009: System MUST automatically reconnect after connection loss
 */
function setupConnectivityListeners() {
    // Listen for online/offline events
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Set initial state
    state.isOnline = navigator.onLine;
    if (!state.isOnline) {
        handleOffline();
    }
}

/**
 * Phase 7 (T059): Handle coming back online
 *
 * SC-007: Automatic reconnection within 5 seconds
 * Feature 1021 (T018): Show skeleton overlay on SSE reconnection
 */
function handleOnline() {
    console.log('Network: Online');
    state.isOnline = true;

    // Reset retry counter for fresh reconnection attempt
    state.sseRetries = 0;

    // Clear any pending reconnect timers
    if (state.reconnectTimer) {
        clearTimeout(state.reconnectTimer);
        state.reconnectTimer = null;
    }

    // Attempt immediate reconnection to SSE
    if (!state.eventSource || state.eventSource.readyState === EventSource.CLOSED) {
        console.log('Reconnecting SSE after coming online...');
        // Feature 1021 (T018): Show skeleton overlay during reconnection
        // Using overlay mode preserves existing content (T017)
        showSkeleton('chart');
        connectSSE();
    }

    updateConnectionMode('connecting');
}

/**
 * Phase 7 (T059): Handle going offline
 *
 * FR-009: Dashboard remains functional during connectivity issues
 */
function handleOffline() {
    console.log('Network: Offline');
    state.isOnline = false;

    // Close SSE connection if active
    if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
    }

    // Stop polling (no point when offline)
    if (state.pollInterval) {
        clearInterval(state.pollInterval);
        state.pollInterval = null;
    }

    // Clear reconnect timers
    if (state.reconnectTimer) {
        clearTimeout(state.reconnectTimer);
        state.reconnectTimer = null;
    }

    updateConnectionMode('offline');
    console.log('Cached data remains accessible via IndexedDB');
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
 * Feature 1050: Uses X-User-ID header for anonymous session authentication.
 * Session is initialized by initSession() before this function is called.
 */
async function fetchMetrics() {
    try {
        // Feature 1050 (FR-003): Include X-User-ID header for authentication
        const options = {
            headers: {
                'X-User-ID': sessionUserId
            }
        };

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
 *
 * Feature 1021 (T011): Hide skeletons when data arrives
 */
function updateMetrics(data) {
    // Feature 1021: Hide metrics skeleton when data arrives
    skeletonSuccess('metrics');
    skeletonSuccess('sentimentChart');
    skeletonSuccess('tagChart');

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
 *
 * Feature 1021 (T011): Hide table skeleton when data arrives
 */
function updateRecentItems(items) {
    // Feature 1021: Hide table skeleton when data arrives
    skeletonSuccess('table');

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
 * Phase 7 (T057): Enhanced with exponential backoff (1s, 2s, 4s, 8s cap)
 * Uses SSE_BASE_URL for the SSE Lambda (two-Lambda architecture).
 * Falls back to API_BASE_URL if SSE_BASE_URL is not configured.
 *
 * Canonical Source: [CS-007] MDN Server-Sent Events
 */
function connectSSE() {
    // Phase 7: Don't attempt connection if offline
    if (!state.isOnline) {
        console.log('Cannot connect SSE: offline');
        updateConnectionMode('offline');
        return;
    }

    if (state.eventSource) {
        state.eventSource.close();
    }

    console.log('Connecting to SSE stream...');
    updateConnectionMode('connecting');

    // Use SSE_BASE_URL if configured, otherwise fall back to API_BASE_URL
    const baseUrl = CONFIG.SSE_BASE_URL || CONFIG.API_BASE_URL;
    const streamUrl = `${baseUrl}${CONFIG.ENDPOINTS.STREAM}`;
    console.log('SSE stream URL:', streamUrl);
    state.eventSource = new EventSource(streamUrl);

    state.eventSource.onopen = () => {
        console.log('SSE connection established');
        state.sseRetries = 0;
        updateConnectionStatus(true);
        updateConnectionMode('streaming');

        // Feature 1021 (T019): Hide skeleton when SSE connected
        hideSkeleton('chart');

        // Clear fallback polling if active
        if (state.pollInterval) {
            clearInterval(state.pollInterval);
            state.pollInterval = null;
        }

        // Clear any pending reconnect timers
        if (state.reconnectTimer) {
            clearTimeout(state.reconnectTimer);
            state.reconnectTimer = null;
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

        // Phase 7: Don't retry if we went offline
        if (!state.isOnline) {
            updateConnectionMode('offline');
            return;
        }

        // Phase 7 (T057): Retry with exponential backoff (1s, 2s, 4s, 8s cap)
        if (state.sseRetries < CONFIG.SSE_MAX_RETRIES) {
            state.sseRetries++;
            // Calculate delay with 8 second cap per spec
            const rawDelay = CONFIG.SSE_RECONNECT_DELAY * Math.pow(2, state.sseRetries - 1);
            const delay = Math.min(rawDelay, 8000);  // Cap at 8 seconds per spec
            console.log(`Retrying SSE connection in ${delay}ms (attempt ${state.sseRetries}/${CONFIG.SSE_MAX_RETRIES})`);
            updateConnectionMode('connecting');
            state.reconnectTimer = setTimeout(connectSSE, delay);
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
 * Phase 7 (T058): Start polling as fallback when SSE fails
 *
 * FR-010: System MUST fall back to periodic polling if streaming
 * connection cannot be established.
 *
 * Uses 5-second interval per spec for faster updates in degraded mode.
 */
function startPolling() {
    // Phase 7: Don't poll if offline
    if (!state.isOnline) {
        console.log('Cannot start polling: offline');
        updateConnectionMode('offline');
        return;
    }

    if (state.pollInterval) {
        return; // Already polling
    }

    console.log('Starting polling fallback');
    updateConnectionMode('polling');

    // Use faster 5s interval per spec (FR-010) when in degraded mode
    const FALLBACK_POLL_INTERVAL = 5000;  // 5 seconds per spec

    // Fetch immediately, then poll
    fetchMetrics();

    state.pollInterval = setInterval(async () => {
        if (state.isOnline) {
            await fetchMetrics();
        }
    }, FALLBACK_POLL_INTERVAL);
}

/**
 * Phase 7 (T060): Update connection mode and show appropriate indicator
 *
 * Connection modes:
 * - 'streaming': SSE connected (green indicator)
 * - 'polling': Fallback polling active (yellow indicator)
 * - 'offline': No network connection (red indicator)
 * - 'connecting': Attempting to connect (pulsing indicator)
 *
 * US5 Acceptance: Display a subtle indicator of degraded mode.
 */
function updateConnectionMode(mode) {
    state.connectionMode = mode;

    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');

    // Remove all mode classes
    indicator.classList.remove('connected', 'disconnected', 'polling', 'offline', 'connecting');

    switch (mode) {
        case 'streaming':
            indicator.classList.add('connected');
            text.textContent = 'Connected';
            state.connected = true;
            break;
        case 'polling':
            indicator.classList.add('polling');
            text.textContent = 'Polling';
            state.connected = true;  // Still receiving data
            break;
        case 'offline':
            indicator.classList.add('offline');
            text.textContent = 'Offline';
            state.connected = false;
            break;
        case 'connecting':
            indicator.classList.add('connecting');
            text.textContent = 'Reconnecting...';
            state.connected = false;
            break;
        default:
            indicator.classList.add('disconnected');
            text.textContent = 'Disconnected';
            state.connected = false;
    }

    console.log(`Connection mode: ${mode}`);
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
    // Phase 7: Clear reconnect timer
    if (state.reconnectTimer) {
        clearTimeout(state.reconnectTimer);
    }
    // Phase 7: Remove connectivity listeners
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);
    // Cleanup timeseries module (Feature 1009)
    if (typeof timeseriesManager !== 'undefined') {
        timeseriesManager.destroy();
    }
});
