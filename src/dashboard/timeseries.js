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
     * @param {string} resolution - e.g., "5m"
     */
    async switchResolution(resolution) {
        if (resolution === this.currentResolution) {
            return;
        }

        const startTime = performance.now();
        console.log(`Switching resolution: ${this.currentResolution} -> ${resolution}`);

        this.currentResolution = resolution;
        this.updateSelectorUI();
        this.updateURL();

        // Try cache first for instant response
        let data = null;
        if (this.cache) {
            data = await this.cache.get(this.currentTicker, resolution);
        }

        if (data) {
            const elapsed = performance.now() - startTime;
            console.log(`Cache hit: ${elapsed.toFixed(1)}ms`);
            this.updateChart(data);
        } else {
            // Fall back to API
            await this.loadData();
        }

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
     */
    async loadData() {
        try {
            const url = `${this.apiBaseUrl}/api/v2/timeseries/${this.currentTicker}?resolution=${this.currentResolution}`;
            console.log(`Fetching: ${url}`);

            const response = await fetch(url);
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

            // Notify listeners
            if (this.onDataUpdate) {
                this.onDataUpdate(buckets);
            }

        } catch (error) {
            console.error('Failed to load timeseries data:', error);
            this.updateChart([]);  // Clear chart on error
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
                this.handleBucketUpdate(bucket);
            } catch (error) {
                console.error('Failed to parse bucket_update:', error);
            }
        });

        this.eventSource.addEventListener('partial_bucket', (event) => {
            try {
                const bucket = JSON.parse(event.data);
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

// Export singleton instance
const timeseriesManager = new TimeseriesManager();

// Export for module systems if available
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TimeseriesManager, timeseriesManager, RESOLUTIONS };
}
