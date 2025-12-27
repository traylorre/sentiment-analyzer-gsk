/**
 * Timeseries Module for Sentiment Dashboard
 * ==========================================
 *
 * Canonical Sources:
 * - [CS-005] AWS Lambda Best Practices - Caching in global scope
 * - [CS-006] Yan Cui Lambda Guide - Warm invocation caching
 * - [CS-008] MDN IndexedDB - Client-side storage for offline/instant access
 *
 * Features:
 * - Resolution selector with 8 levels (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h)
 * - Instant resolution switching (<100ms) via IndexedDB cache
 * - OHLC chart rendering with Chart.js
 * - Real-time updates via SSE with resolution filtering
 */

/**
 * Available resolutions for time-series display
 * Duration in seconds used for chart calculations
 */
const RESOLUTIONS = [
    { key: '1m', label: '1 Min', duration: 60 },
    { key: '5m', label: '5 Min', duration: 300 },
    { key: '10m', label: '10 Min', duration: 600 },
    { key: '1h', label: '1 Hour', duration: 3600 },
    { key: '3h', label: '3 Hour', duration: 10800 },
    { key: '6h', label: '6 Hour', duration: 21600 },
    { key: '12h', label: '12 Hour', duration: 43200 },
    { key: '24h', label: '24 Hour', duration: 86400 }
];

/**
 * Default ticker and resolution
 */
const DEFAULT_TICKER = 'AAPL';
const DEFAULT_RESOLUTION = '5m';

/**
 * Feature 1019: Latency tracking for SSE events
 * Exposes window.lastLatencyMetrics and window.latencySamples for E2E testing
 */
window.latencySamples = [];
window.lastLatencyMetrics = null;

/**
 * Calculate and track latency from SSE event origin_timestamp
 *
 * @param {Object} eventData - Parsed SSE event data
 * @param {string} eventType - Type of SSE event
 * @returns {Object|null} Latency metrics or null if no origin_timestamp
 */
function trackLatency(eventData, eventType) {
    if (!eventData.origin_timestamp) {
        return null;
    }

    const receiveTime = Date.now();
    const originTime = new Date(eventData.origin_timestamp).getTime();
    const latencyMs = receiveTime - originTime;
    const isClockSkew = latencyMs < 0;

    const metrics = {
        latency_ms: latencyMs,
        event_type: eventType,
        ticker: eventData.ticker || null,
        origin_timestamp: eventData.origin_timestamp,
        receive_timestamp: new Date(receiveTime).toISOString(),
        is_clock_skew: isClockSkew
    };

    window.lastLatencyMetrics = metrics;

    // Only track positive latency values (non-clock-skew)
    if (!isClockSkew) {
        window.latencySamples.push(latencyMs);
        // Keep only last 1000 samples
        if (window.latencySamples.length > 1000) {
            window.latencySamples.shift();
        }
    }

    return metrics;
}

/**
 * TimeseriesManager - Coordinates resolution switching and data fetching
 */
class TimeseriesManager {
    constructor(config = {}) {
        this.apiBaseUrl = config.apiBaseUrl || (typeof CONFIG !== 'undefined' ? CONFIG.API_BASE_URL : '');
        this.sseBaseUrl = config.sseBaseUrl || (typeof CONFIG !== 'undefined' ? CONFIG.SSE_BASE_URL : '');
        this.cache = typeof timeseriesCache !== 'undefined' ? timeseriesCache : null;

        this.currentTicker = DEFAULT_TICKER;
        this.currentResolution = DEFAULT_RESOLUTION;
        this.chart = null;
        this.eventSource = null;

        this.onDataUpdate = null;  // Callback for data updates
        this.onResolutionChange = null;  // Callback for resolution changes
    }

    /**
     * Initialize timeseries module
     */
    async init() {
        // Initialize cache
        if (this.cache) {
            await this.cache.init();
        }

        // Parse URL params
        const params = new URLSearchParams(window.location.search);
        if (params.has('ticker')) {
            this.currentTicker = params.get('ticker').toUpperCase();
        }
        if (params.has('resolution')) {
            const res = params.get('resolution');
            if (RESOLUTIONS.some(r => r.key === res)) {
                this.currentResolution = res;
            }
        }

        // Create resolution selector UI
        this.renderResolutionSelector();

        // Initialize chart
        this.initChart();

        // Load initial data
        await this.loadData();

        // Connect to SSE with resolution filter
        this.connectSSE();

        console.log(`Timeseries initialized: ${this.currentTicker} @ ${this.currentResolution}`);
    }

    /**
     * Render resolution selector buttons
     */
    renderResolutionSelector() {
        // Find or create container
        let container = document.getElementById('resolution-selector');
        if (!container) {
            // Create container if not in HTML
            const chartsSection = document.querySelector('.charts-row');
            if (chartsSection) {
                container = document.createElement('div');
                container.id = 'resolution-selector';
                container.className = 'resolution-selector';
                chartsSection.parentNode.insertBefore(container, chartsSection);
            } else {
                console.warn('No .charts-row section found for resolution selector');
                return;
            }
        }

        // Clear existing content
        container.innerHTML = `
            <div class="resolution-header">
                <label for="ticker-input">Ticker:</label>
                <input type="text"
                       id="ticker-input"
                       value="${this.currentTicker}"
                       maxlength="10"
                       data-testid="ticker-input">
                <span class="resolution-label">Resolution:</span>
            </div>
            <div class="resolution-buttons" role="group" aria-label="Time resolution">
                ${RESOLUTIONS.map(r => `
                    <button type="button"
                            class="resolution-btn ${r.key === this.currentResolution ? 'active' : ''}"
                            data-resolution="${r.key}"
                            data-testid="resolution-${r.key}"
                            aria-pressed="${r.key === this.currentResolution}">
                        ${r.label}
                    </button>
                `).join('')}
            </div>
        `;

        // Add event listeners
        container.querySelectorAll('.resolution-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const resolution = e.target.dataset.resolution;
                this.switchResolution(resolution);
            });
        });

        // Ticker input handler
        const tickerInput = document.getElementById('ticker-input');
        if (tickerInput) {
            tickerInput.addEventListener('change', (e) => {
                const ticker = e.target.value.toUpperCase().trim();
                if (ticker && ticker !== this.currentTicker) {
                    this.switchTicker(ticker);
                }
            });
            tickerInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.target.blur();  // Trigger change event
                }
            });
        }
    }

    /**
     * Update resolution selector UI to reflect current selection
     */
    updateSelectorUI() {
        document.querySelectorAll('.resolution-btn').forEach(btn => {
            const isActive = btn.dataset.resolution === this.currentResolution;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive);
        });

        const tickerInput = document.getElementById('ticker-input');
        if (tickerInput) {
            tickerInput.value = this.currentTicker;
        }
    }

    /**
     * Switch to a new resolution
     * Attempts cache-first for instant switching
     *
     * Feature 1021 (T013-T016): Show skeleton during resolution switch
     *
     * @param {string} resolution - e.g., "5m"
     */
    async switchResolution(resolution) {
        if (resolution === this.currentResolution) {
            return;
        }

        // Feature 1021 (T014): Debounce rapid resolution switches
        if (this._resolutionDebounce) {
            clearTimeout(this._resolutionDebounce);
        }

        const debounceMs = (typeof CONFIG !== 'undefined' && CONFIG.SKELETON)
            ? CONFIG.SKELETON.DEBOUNCE_MS
            : 300;

        this._resolutionDebounce = setTimeout(async () => {
            await this._performResolutionSwitch(resolution);
        }, debounceMs);
    }

    /**
     * Internal method to perform the actual resolution switch
     * Called after debounce delay
     */
    async _performResolutionSwitch(resolution) {
        // Performance instrumentation: mark start (T064)
        const switchId = `resolution-switch-${Date.now()}`;
        performance.mark(`${switchId}-start`);

        const previousResolution = this.currentResolution;
        console.log(`Switching resolution: ${previousResolution} -> ${resolution}`);

        this.currentResolution = resolution;
        this.updateSelectorUI();
        this.updateURL();

        // Try cache first for instant response
        let data = null;
        let cacheHit = false;
        if (this.cache) {
            data = await this.cache.get(this.currentTicker, resolution);
            cacheHit = data !== null;
        }

        if (data) {
            this.updateChart(data);
            // Feature 1021: No skeleton needed for cache hit (instant)
        } else {
            // Feature 1021 (T013): Show skeleton during API fetch
            if (typeof showSkeleton === 'function') {
                showSkeleton('chart');
            }
            // Fall back to API
            await this.loadData();
        }

        // Performance instrumentation: mark end and measure
        performance.mark(`${switchId}-end`);
        performance.measure(switchId, `${switchId}-start`, `${switchId}-end`);

        const entries = performance.getEntriesByName(switchId, 'measure');
        const duration = entries.length > 0 ? entries[0].duration : 0;

        // Expose metrics for E2E tests
        window.lastSwitchMetrics = {
            duration_ms: duration,
            from_resolution: previousResolution,
            to_resolution: resolution,
            cache_hit: cacheHit,
            timestamp: Date.now()
        };

        console.log(`Resolution switch completed in ${duration.toFixed(1)}ms (cache: ${cacheHit})`);

        // Clean up performance entries to avoid memory leak
        performance.clearMarks(`${switchId}-start`);
        performance.clearMarks(`${switchId}-end`);
        performance.clearMeasures(switchId);

        // Reconnect SSE with new resolution filter
        this.connectSSE();

        // Notify listeners
        if (this.onResolutionChange) {
            this.onResolutionChange(resolution);
        }
    }

    /**
     * Switch to a new ticker
     */
    async switchTicker(ticker) {
        if (ticker === this.currentTicker) {
            return;
        }

        console.log(`Switching ticker: ${this.currentTicker} -> ${ticker}`);

        this.currentTicker = ticker;
        this.updateSelectorUI();
        this.updateURL();

        // Clear and reload data
        await this.loadData();

        // Reconnect SSE for new ticker
        this.connectSSE();

        // Feature 1057: Update OHLC chart when ticker changes
        if (typeof updateOHLCTicker === 'function') {
            await updateOHLCTicker(ticker);
        }
    }

    /**
     * Update URL with current state (without page reload)
     */
    updateURL() {
        const url = new URL(window.location);
        url.searchParams.set('ticker', this.currentTicker);
        url.searchParams.set('resolution', this.currentResolution);
        window.history.replaceState({}, '', url);
    }

    /**
     * Load timeseries data from API
     *
     * Feature 1021 (T015): Hide skeleton when data arrives
     * Feature 1051: Added X-User-ID header for session auth
     */
    async loadData() {
        try {
            const url = `${this.apiBaseUrl}/api/v2/timeseries/${this.currentTicker}?resolution=${this.currentResolution}`;
            console.log(`Fetching: ${url}`);

            // Feature 1051: Include X-User-ID header for authentication
            const response = await fetch(url, {
                headers: {
                    'X-User-ID': sessionUserId
                }
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            const buckets = data.buckets || [];

            // Cache the response
            if (this.cache && buckets.length > 0) {
                await this.cache.set(this.currentTicker, this.currentResolution, buckets);
            }

            // Update chart
            this.updateChart(buckets);

            // Feature 1021 (T015): Hide skeleton when data arrives
            if (typeof skeletonSuccess === 'function') {
                skeletonSuccess('chart');
            }

            // Notify listeners
            if (this.onDataUpdate) {
                this.onDataUpdate(buckets);
            }

        } catch (error) {
            console.error('Failed to load timeseries data:', error);
            this.updateChart([]);  // Clear chart on error
            // Feature 1021: Hide skeleton on error too
            if (typeof hideSkeleton === 'function') {
                hideSkeleton('chart');
            }
        }
    }

    /**
     * Initialize Chart.js OHLC chart
     */
    initChart() {
        // Find or create chart container
        let chartContainer = document.getElementById('timeseries-chart-container');
        if (!chartContainer) {
            const chartsSection = document.querySelector('.charts-row');
            if (chartsSection) {
                chartContainer = document.createElement('div');
                chartContainer.id = 'timeseries-chart-container';
                chartContainer.className = 'chart-container timeseries-chart';
                chartContainer.innerHTML = `
                    <h3>Sentiment Trend <span id="timeseries-ticker">${this.currentTicker}</span></h3>
                    <canvas id="timeseries-chart" data-testid="timeseries-chart"></canvas>
                    <div id="chart-loaded" data-testid="chart-loaded" style="display:none;"></div>
                `;
                chartsSection.appendChild(chartContainer);
            }
        }

        const canvas = document.getElementById('timeseries-chart');
        if (!canvas) {
            console.warn('Timeseries chart canvas not found');
            return;
        }

        const ctx = canvas.getContext('2d');

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Avg Sentiment',
                        data: [],
                        borderColor: 'rgba(75, 192, 192, 1)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'High',
                        data: [],
                        borderColor: 'rgba(46, 204, 113, 0.6)',
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false
                    },
                    {
                        label: 'Low',
                        data: [],
                        borderColor: 'rgba(231, 76, 60, 0.6)',
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Sentiment Score'
                        },
                        min: -1,
                        max: 1
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            afterBody: (items) => {
                                if (items.length > 0 && this._currentBuckets) {
                                    const index = items[0].dataIndex;
                                    const bucket = this._currentBuckets[index];
                                    if (bucket) {
                                        return [
                                            `Count: ${bucket.count || 0}`,
                                            `Positive: ${bucket.label_counts?.positive || 0}`,
                                            `Negative: ${bucket.label_counts?.negative || 0}`,
                                            `Neutral: ${bucket.label_counts?.neutral || 0}`
                                        ];
                                    }
                                }
                                return [];
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Update chart with bucket data
     */
    updateChart(buckets) {
        if (!this.chart) {
            return;
        }

        this._currentBuckets = buckets;

        // Update ticker label
        const tickerLabel = document.getElementById('timeseries-ticker');
        if (tickerLabel) {
            tickerLabel.textContent = this.currentTicker;
        }

        // Format labels and data
        const labels = buckets.map(b => {
            const ts = b.bucket_timestamp || b.SK;
            const date = new Date(ts);
            // Format based on resolution
            if (['1m', '5m', '10m'].includes(this.currentResolution)) {
                return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
            } else if (['1h', '3h', '6h'].includes(this.currentResolution)) {
                return date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit' });
            } else {
                return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
            }
        });

        const avgData = buckets.map(b => b.avg !== undefined ? b.avg : (b.sum / b.count) || 0);
        const highData = buckets.map(b => b.high || 0);
        const lowData = buckets.map(b => b.low || 0);

        this.chart.data.labels = labels;
        this.chart.data.datasets[0].data = avgData;
        this.chart.data.datasets[1].data = highData;
        this.chart.data.datasets[2].data = lowData;
        this.chart.update('none');  // No animation for fast updates

        // Signal chart is loaded (for E2E tests)
        const loadedIndicator = document.getElementById('chart-loaded');
        if (loadedIndicator) {
            loadedIndicator.style.display = 'block';
            loadedIndicator.dataset.timestamp = Date.now();
        }
    }

    /**
     * Connect to SSE stream with resolution filter [CS-007]
     */
    connectSSE() {
        // Close existing connection
        if (this.eventSource) {
            this.eventSource.close();
        }

        const baseUrl = this.sseBaseUrl || this.apiBaseUrl;
        if (!baseUrl) {
            console.warn('No SSE base URL configured');
            return;
        }

        // Connect with resolution filter
        const streamUrl = `${baseUrl}/api/v2/stream?tickers=${this.currentTicker}&resolutions=${this.currentResolution}`;
        console.log('Connecting to SSE:', streamUrl);

        this.eventSource = new EventSource(streamUrl);

        this.eventSource.addEventListener('bucket_update', (event) => {
            try {
                const bucket = JSON.parse(event.data);
                // Feature 1019: Track latency for E2E validation
                trackLatency(bucket, 'bucket_update');
                this.handleBucketUpdate(bucket);
            } catch (error) {
                console.error('Failed to parse bucket_update:', error);
            }
        });

        this.eventSource.addEventListener('partial_bucket', (event) => {
            try {
                const bucket = JSON.parse(event.data);
                // Feature 1019: Track latency for E2E validation
                trackLatency(bucket, 'partial_bucket');
                this.handlePartialBucket(bucket);
            } catch (error) {
                console.error('Failed to parse partial_bucket:', error);
            }
        });

        this.eventSource.onerror = (error) => {
            console.error('Timeseries SSE error:', error);
            // Will auto-reconnect
        };
    }

    /**
     * Handle completed bucket update from SSE
     */
    handleBucketUpdate(bucket) {
        if (bucket.ticker !== this.currentTicker || bucket.resolution !== this.currentResolution) {
            return;  // Filtered by server, but double-check
        }

        console.log('Bucket update:', bucket);

        // Update cache
        if (this.cache) {
            this.cache.set(this.currentTicker, this.currentResolution, [bucket]).catch(console.error);
        }

        // Append to chart
        if (this._currentBuckets) {
            // Check if bucket already exists
            const existingIdx = this._currentBuckets.findIndex(
                b => (b.bucket_timestamp || b.SK) === (bucket.bucket_timestamp || bucket.SK)
            );
            if (existingIdx >= 0) {
                this._currentBuckets[existingIdx] = bucket;
            } else {
                this._currentBuckets.push(bucket);
            }
            this.updateChart(this._currentBuckets);
        }
    }

    /**
     * Handle partial bucket update (in-progress aggregation)
     */
    handlePartialBucket(bucket) {
        // Partial buckets show live progress but don't update cache
        console.log('Partial bucket:', bucket);

        // Could show with different styling or update last point
        // For now, treat same as complete bucket for chart update
        this.handleBucketUpdate(bucket);
    }

    /**
     * Clean up resources
     */
    destroy() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }
}

/**
 * MultiTickerManager - Manages multiple ticker charts for comparison view
 * Feature 1009 Phase 6 (T052): Multi-ticker chart layout
 *
 * Canonical Sources:
 * - [CS-002] ticker#resolution composite key for filtering
 * - [CS-006] Shared caching across users
 */
class MultiTickerManager {
    constructor(config = {}) {
        this.apiBaseUrl = config.apiBaseUrl || (typeof CONFIG !== 'undefined' ? CONFIG.API_BASE_URL : '');
        this.sseBaseUrl = config.sseBaseUrl || (typeof CONFIG !== 'undefined' ? CONFIG.SSE_BASE_URL : '');
        this.cache = typeof timeseriesCache !== 'undefined' ? timeseriesCache : null;

        this.tickers = [];  // Array of ticker symbols
        this.currentResolution = DEFAULT_RESOLUTION;
        this.charts = {};   // ticker -> Chart instance
        this.bucketData = {};  // ticker -> buckets array
        this.eventSource = null;

        // Callbacks
        this.onDataUpdate = null;
    }

    /**
     * Initialize multi-ticker view
     * @param {string[]} tickers - Array of ticker symbols
     */
    async init(tickers = ['AAPL', 'MSFT', 'GOOGL']) {
        this.tickers = tickers.map(t => t.toUpperCase());

        // Initialize cache
        if (this.cache) {
            await this.cache.init();
        }

        // Parse URL params
        const params = new URLSearchParams(window.location.search);
        if (params.has('tickers')) {
            this.tickers = params.get('tickers').toUpperCase().split(',').filter(t => t.trim());
        }
        if (params.has('resolution')) {
            const res = params.get('resolution');
            if (RESOLUTIONS.some(r => r.key === res)) {
                this.currentResolution = res;
            }
        }

        // Render UI
        this.renderCompareUI();

        // Load all ticker data in parallel (SC-006: <1s for 10 tickers)
        await this.loadAllData();

        // Connect SSE for all tickers
        this.connectSSE();

        console.log(`Multi-ticker view initialized: ${this.tickers.join(', ')} @ ${this.currentResolution}`);
    }

    /**
     * Render multi-ticker comparison UI
     */
    renderCompareUI() {
        // Find or create container
        let container = document.getElementById('multi-ticker-container');
        if (!container) {
            const chartsSection = document.querySelector('.charts-row');
            if (chartsSection) {
                container = document.createElement('div');
                container.id = 'multi-ticker-container';
                container.className = 'multi-ticker-container';
                chartsSection.parentNode.insertBefore(container, chartsSection.nextSibling);
            } else {
                console.warn('No .charts-row section found for multi-ticker view');
                return;
            }
        }

        // Header with resolution selector and ticker input
        container.innerHTML = `
            <div class="multi-ticker-header">
                <h3>Compare Tickers</h3>
                <div class="ticker-input-row">
                    <label for="multi-ticker-input">Tickers (comma-separated):</label>
                    <input type="text"
                           id="multi-ticker-input"
                           value="${this.tickers.join(', ')}"
                           placeholder="AAPL, MSFT, GOOGL"
                           data-testid="multi-ticker-input">
                    <button type="button" id="update-tickers-btn" data-testid="update-tickers">
                        Update
                    </button>
                </div>
                <div class="resolution-buttons" role="group" aria-label="Time resolution">
                    ${RESOLUTIONS.map(r => `
                        <button type="button"
                                class="resolution-btn ${r.key === this.currentResolution ? 'active' : ''}"
                                data-resolution="${r.key}"
                                data-testid="compare-resolution-${r.key}"
                                aria-pressed="${r.key === this.currentResolution}">
                            ${r.label}
                        </button>
                    `).join('')}
                </div>
            </div>
            <div id="ticker-charts-grid" class="ticker-charts-grid" data-testid="ticker-charts-grid">
                ${this.tickers.map(ticker => `
                    <div class="ticker-chart-cell" data-ticker="${ticker}" data-testid="chart-cell-${ticker}">
                        <h4>${ticker}</h4>
                        <canvas id="chart-${ticker}" data-testid="chart-${ticker}"></canvas>
                        <div class="chart-status" id="status-${ticker}">Loading...</div>
                    </div>
                `).join('')}
            </div>
        `;

        // Add event listeners for resolution buttons
        container.querySelectorAll('.resolution-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const resolution = e.target.dataset.resolution;
                this.switchResolution(resolution);
            });
        });

        // Ticker input update button
        const updateBtn = document.getElementById('update-tickers-btn');
        if (updateBtn) {
            updateBtn.addEventListener('click', () => this.updateTickers());
        }

        // Allow Enter key to update
        const tickerInput = document.getElementById('multi-ticker-input');
        if (tickerInput) {
            tickerInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.updateTickers();
                }
            });
        }

        // Initialize charts for each ticker
        this.tickers.forEach(ticker => {
            this.initTickerChart(ticker);
        });
    }

    /**
     * Initialize Chart.js instance for a single ticker
     */
    initTickerChart(ticker) {
        const canvas = document.getElementById(`chart-${ticker}`);
        if (!canvas) {
            console.warn(`Canvas not found for ticker: ${ticker}`);
            return;
        }

        const ctx = canvas.getContext('2d');
        this.charts[ticker] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: ticker,
                    data: [],
                    borderColor: this.getTickerColor(ticker),
                    backgroundColor: this.getTickerColor(ticker, 0.2),
                    tension: 0.3,
                    fill: true,
                    pointRadius: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    y: {
                        min: -1,
                        max: 1,
                        title: { display: false }
                    },
                    x: {
                        display: true,
                        ticks: { maxTicksLimit: 6 }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => items[0]?.label || '',
                            label: (context) => `Sentiment: ${context.raw?.toFixed(3) || 'N/A'}`
                        }
                    }
                }
            }
        });
    }

    /**
     * Get a unique color for each ticker
     */
    getTickerColor(ticker, alpha = 1) {
        const colors = [
            `rgba(75, 192, 192, ${alpha})`,   // teal
            `rgba(54, 162, 235, ${alpha})`,   // blue
            `rgba(255, 159, 64, ${alpha})`,   // orange
            `rgba(153, 102, 255, ${alpha})`,  // purple
            `rgba(255, 99, 132, ${alpha})`,   // red
            `rgba(255, 205, 86, ${alpha})`,   // yellow
            `rgba(201, 203, 207, ${alpha})`,  // gray
            `rgba(46, 204, 113, ${alpha})`,   // green
            `rgba(241, 90, 34, ${alpha})`,    // vermilion
            `rgba(155, 89, 182, ${alpha})`    // violet
        ];
        const index = this.tickers.indexOf(ticker) % colors.length;
        return colors[index];
    }

    /**
     * Load all ticker data using batch API (SC-006: <1s for 10 tickers)
     * Feature 1051: Added X-User-ID header for session auth
     */
    async loadAllData() {
        const startTime = performance.now();

        try {
            // Use batch endpoint for parallel queries
            const tickersParam = this.tickers.join(',');
            const url = `${this.apiBaseUrl}/api/v2/timeseries/batch?tickers=${tickersParam}&resolution=${this.currentResolution}`;
            console.log(`Batch fetching: ${url}`);

            // Feature 1051: Include X-User-ID header for authentication
            const response = await fetch(url, {
                headers: {
                    'X-User-ID': sessionUserId
                }
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            // Update each ticker's chart
            for (const ticker of this.tickers) {
                const tickerData = data[ticker];
                if (tickerData && tickerData.buckets) {
                    this.bucketData[ticker] = tickerData.buckets;
                    this.updateTickerChart(ticker, tickerData.buckets);

                    // Cache for instant resolution switching
                    if (this.cache) {
                        await this.cache.set(ticker, this.currentResolution, tickerData.buckets);
                    }
                } else {
                    this.updateTickerStatus(ticker, 'No data');
                }
            }

            const elapsed = performance.now() - startTime;
            console.log(`Batch load complete: ${elapsed.toFixed(0)}ms for ${this.tickers.length} tickers`);

            // Verify SC-006 metric
            if (elapsed > 1000 && this.tickers.length <= 10) {
                console.warn(`SC-006 violation: ${elapsed.toFixed(0)}ms > 1000ms for ${this.tickers.length} tickers`);
            }

        } catch (error) {
            console.error('Failed to load batch data:', error);
            // Fallback to individual requests
            await this.loadAllDataFallback();
        }
    }

    /**
     * Fallback: load data individually if batch fails
     * Feature 1051: Added X-User-ID header for session auth
     */
    async loadAllDataFallback() {
        console.log('Using fallback individual requests');

        const promises = this.tickers.map(async (ticker) => {
            try {
                const url = `${this.apiBaseUrl}/api/v2/timeseries/${ticker}?resolution=${this.currentResolution}`;
                // Feature 1051: Include X-User-ID header for authentication
                const response = await fetch(url, {
                    headers: {
                        'X-User-ID': sessionUserId
                    }
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                this.bucketData[ticker] = data.buckets || [];
                this.updateTickerChart(ticker, data.buckets || []);
            } catch (error) {
                console.error(`Failed to load ${ticker}:`, error);
                this.updateTickerStatus(ticker, 'Error');
            }
        });

        await Promise.all(promises);
    }

    /**
     * Update a single ticker's chart
     */
    updateTickerChart(ticker, buckets) {
        const chart = this.charts[ticker];
        if (!chart) return;

        if (!buckets || buckets.length === 0) {
            this.updateTickerStatus(ticker, 'No data');
            return;
        }

        const labels = buckets.map(b => {
            const ts = b.bucket_timestamp || b.SK;
            const date = new Date(ts);
            if (['1m', '5m', '10m'].includes(this.currentResolution)) {
                return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
            } else {
                return date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit' });
            }
        });

        const avgData = buckets.map(b => b.avg !== undefined ? b.avg : (b.sum / b.count) || 0);

        chart.data.labels = labels;
        chart.data.datasets[0].data = avgData;
        chart.update('none');

        this.updateTickerStatus(ticker, `${buckets.length} points`);
    }

    /**
     * Update status text for a ticker
     */
    updateTickerStatus(ticker, status) {
        const statusEl = document.getElementById(`status-${ticker}`);
        if (statusEl) {
            statusEl.textContent = status;
        }
    }

    /**
     * Switch resolution for all tickers
     */
    async switchResolution(resolution) {
        if (resolution === this.currentResolution) return;

        // Performance instrumentation: mark start
        const switchId = `multi-resolution-switch-${Date.now()}`;
        performance.mark(`${switchId}-start`);

        const previousResolution = this.currentResolution;
        console.log(`Switching resolution: ${previousResolution} -> ${resolution}`);
        this.currentResolution = resolution;

        // Update UI
        document.querySelectorAll('#multi-ticker-container .resolution-btn').forEach(btn => {
            const isActive = btn.dataset.resolution === resolution;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive);
        });

        this.updateURL();

        // Try cache first for instant switching
        let allCached = true;
        for (const ticker of this.tickers) {
            if (this.cache) {
                const cached = await this.cache.get(ticker, resolution);
                if (cached) {
                    this.bucketData[ticker] = cached;
                    this.updateTickerChart(ticker, cached);
                } else {
                    allCached = false;
                }
            } else {
                allCached = false;
            }
        }

        // If not all cached, reload from API
        if (!allCached) {
            await this.loadAllData();
        }

        // Performance instrumentation: mark end and measure
        performance.mark(`${switchId}-end`);
        performance.measure(switchId, `${switchId}-start`, `${switchId}-end`);

        const entries = performance.getEntriesByName(switchId, 'measure');
        const duration = entries.length > 0 ? entries[0].duration : 0;

        // Expose metrics for E2E tests
        window.lastSwitchMetrics = {
            duration_ms: duration,
            from_resolution: previousResolution,
            to_resolution: resolution,
            cache_hit: allCached,
            timestamp: Date.now()
        };

        console.log(`Multi-ticker resolution switch completed in ${duration.toFixed(1)}ms (all cached: ${allCached})`);

        // Clean up performance entries to avoid memory leak
        performance.clearMarks(`${switchId}-start`);
        performance.clearMarks(`${switchId}-end`);
        performance.clearMeasures(switchId);

        // Reconnect SSE
        this.connectSSE();
    }

    /**
     * Update tickers from input field
     */
    async updateTickers() {
        const input = document.getElementById('multi-ticker-input');
        if (!input) return;

        const newTickers = input.value.toUpperCase()
            .split(',')
            .map(t => t.trim())
            .filter(t => t.length > 0);

        if (newTickers.length === 0) {
            console.warn('No valid tickers entered');
            return;
        }

        // Check for changes
        const tickersChanged = JSON.stringify(this.tickers) !== JSON.stringify(newTickers);
        if (!tickersChanged) return;

        this.tickers = newTickers;
        this.updateURL();

        // Re-render grid and reload
        this.renderCompareUI();
        await this.loadAllData();
        this.connectSSE();
    }

    /**
     * Update URL with current state
     */
    updateURL() {
        const url = new URL(window.location);
        url.searchParams.set('tickers', this.tickers.join(','));
        url.searchParams.set('resolution', this.currentResolution);
        window.history.replaceState({}, '', url);
    }

    /**
     * Connect SSE for all tickers with resolution filter
     */
    connectSSE() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        const baseUrl = this.sseBaseUrl || this.apiBaseUrl;
        if (!baseUrl) return;

        // Use new tickers query param (T051)
        const tickersParam = this.tickers.join(',');
        const streamUrl = `${baseUrl}/api/v2/stream?tickers=${tickersParam}&resolutions=${this.currentResolution}`;
        console.log('Multi-ticker SSE connecting:', streamUrl);

        this.eventSource = new EventSource(streamUrl);

        this.eventSource.addEventListener('bucket_update', (event) => {
            try {
                const bucket = JSON.parse(event.data);
                this.handleBucketUpdate(bucket);
            } catch (error) {
                console.error('Failed to parse bucket_update:', error);
            }
        });

        this.eventSource.addEventListener('partial_bucket', (event) => {
            try {
                const bucket = JSON.parse(event.data);
                this.handleBucketUpdate(bucket);  // Treat same as full update
            } catch (error) {
                console.error('Failed to parse partial_bucket:', error);
            }
        });

        this.eventSource.onerror = (error) => {
            console.error('Multi-ticker SSE error:', error);
        };
    }

    /**
     * Handle bucket update for any ticker
     */
    handleBucketUpdate(bucket) {
        const ticker = bucket.ticker;
        if (!this.tickers.includes(ticker)) return;
        if (bucket.resolution !== this.currentResolution) return;

        console.log(`Bucket update for ${ticker}:`, bucket);

        // Update bucket data
        if (!this.bucketData[ticker]) {
            this.bucketData[ticker] = [];
        }

        const existingIdx = this.bucketData[ticker].findIndex(
            b => (b.bucket_timestamp || b.SK) === (bucket.bucket_timestamp || bucket.SK)
        );

        if (existingIdx >= 0) {
            this.bucketData[ticker][existingIdx] = bucket;
        } else {
            this.bucketData[ticker].push(bucket);
        }

        this.updateTickerChart(ticker, this.bucketData[ticker]);
    }

    /**
     * Clean up resources
     */
    destroy() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};
    }
}

// Export singleton instances
const timeseriesManager = new TimeseriesManager();
const multiTickerManager = new MultiTickerManager();

/**
 * Set sentiment timeseries resolution (Feature 1064: unified resolution selector)
 * Called from unified-resolution.js to update sentiment chart resolution
 * @param {string} resolution - Sentiment resolution value ('1m', '5m', '10m', '1h', etc.)
 * @param {boolean} isFallback - True if this is a fallback from a different unified resolution
 */
async function setSentimentResolution(resolution, isFallback = false) {
    if (!timeseriesManager) {
        console.warn('Timeseries manager not initialized');
        return;
    }

    console.log(`Sentiment: External resolution set to ${resolution}${isFallback ? ' (fallback)' : ''}`);

    // Use the existing switchResolution method
    await timeseriesManager.switchResolution(resolution);

    // Show fallback indicator if needed (future enhancement)
    if (isFallback) {
        console.log('Sentiment: Resolution mapped from unified selector');
    }
}

/**
 * Hide the local sentiment resolution selector (Feature 1064)
 * Called when unified resolution selector is active
 */
function hideSentimentResolutionSelector() {
    const container = document.getElementById('resolution-selector');
    if (container) {
        container.style.display = 'none';
    }
}

/**
 * Get the timeseries manager instance
 */
function getTimeseriesManager() {
    return timeseriesManager;
}

// Export functions for external use (Feature 1064)
window.setSentimentResolution = setSentimentResolution;
window.hideSentimentResolutionSelector = hideSentimentResolutionSelector;
window.getTimeseriesManager = getTimeseriesManager;

// Export for module systems if available
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        TimeseriesManager,
        MultiTickerManager,
        timeseriesManager,
        multiTickerManager,
        RESOLUTIONS,
        setSentimentResolution,
        hideSentimentResolutionSelector
    };
}
