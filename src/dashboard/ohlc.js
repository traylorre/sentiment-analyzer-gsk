/**
 * OHLC Chart Module (Feature 1057, 1065)
 * ======================================
 *
 * Displays OHLC candlestick price data with time resolution selector.
 * Feature 1065: Overlays sentiment trend line on the price chart.
 * Integrates with existing dashboard session auth and ticker input.
 *
 * Dependencies:
 * - Chart.js (loaded in index.html)
 * - config.js (CONFIG object)
 * - app.js (sessionUserId)
 */

/**
 * Storage key for OHLC resolution preference
 */
const OHLC_RESOLUTION_KEY = 'ohlc_preferred_resolution';

/**
 * OHLCChart class - manages OHLC candlestick chart display
 */
class OHLCChart {
    constructor(options = {}) {
        this.apiBaseUrl = options.apiBaseUrl || CONFIG.API_BASE_URL;
        this.currentTicker = options.ticker || 'AAPL';
        this.currentResolution = this.loadResolutionPreference();
        this.chart = null;
        this.isLoading = false;
        this.lastError = null;
        this.fallbackMessage = null;

        // Feature 1065: Sentiment overlay state
        this.sentimentData = [];
        this.sentimentResolution = null;  // Mapped from unified resolution
        this.ohlcCandles = [];  // Store raw candle data for alignment

        // Callbacks
        this.onTickerChange = options.onTickerChange || null;
        this.onResolutionChange = options.onResolutionChange || null;
    }

    /**
     * Load resolution preference from sessionStorage
     */
    loadResolutionPreference() {
        try {
            const saved = sessionStorage.getItem(OHLC_RESOLUTION_KEY);
            if (saved && CONFIG.OHLC_RESOLUTIONS.some(r => r.key === saved)) {
                return saved;
            }
        } catch (e) {
            console.warn('Could not load OHLC resolution preference:', e.message);
        }
        return CONFIG.DEFAULT_OHLC_RESOLUTION;
    }

    /**
     * Save resolution preference to sessionStorage
     */
    saveResolutionPreference(resolution) {
        try {
            sessionStorage.setItem(OHLC_RESOLUTION_KEY, resolution);
        } catch (e) {
            console.warn('Could not save OHLC resolution preference:', e.message);
        }
    }

    /**
     * Initialize the chart and UI
     */
    async init() {
        console.log('Initializing OHLC chart...');

        // Render resolution selector
        this.renderResolutionSelector();

        // Initialize Chart.js chart
        this.initChart();

        // Bind event handlers
        this.bindEvents();

        // Load initial data
        await this.loadData();

        console.log(`OHLC chart initialized: ${this.currentTicker} @ ${this.currentResolution}`);
    }

    /**
     * Render the resolution selector buttons
     */
    renderResolutionSelector() {
        const container = document.getElementById('ohlc-resolution-selector');
        if (!container) {
            console.warn('OHLC resolution selector container not found');
            return;
        }

        const buttonsHtml = CONFIG.OHLC_RESOLUTIONS.map(r => `
            <button
                class="ohlc-resolution-btn ${r.key === this.currentResolution ? 'active' : ''}"
                data-resolution="${r.key}"
                title="${r.description}"
                aria-pressed="${r.key === this.currentResolution}">
                ${r.label}
            </button>
        `).join('');

        container.innerHTML = `
            <div class="ohlc-resolution-header">
                <span class="ohlc-resolution-label">Price Resolution:</span>
            </div>
            <div class="ohlc-resolution-buttons" role="group" aria-label="OHLC time resolution">
                ${buttonsHtml}
            </div>
        `;
    }

    /**
     * Update resolution selector UI to reflect current selection
     */
    updateSelectorUI() {
        const buttons = document.querySelectorAll('.ohlc-resolution-btn');
        buttons.forEach(btn => {
            const isActive = btn.dataset.resolution === this.currentResolution;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive);
        });

        // Update ticker display
        const tickerLabel = document.getElementById('ohlc-ticker-label');
        if (tickerLabel) {
            tickerLabel.textContent = this.currentTicker;
        }
    }

    /**
     * Bind event handlers for resolution buttons and chart interactions
     */
    bindEvents() {
        // Resolution button clicks
        document.querySelectorAll('.ohlc-resolution-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const resolution = btn.dataset.resolution;
                if (resolution !== this.currentResolution) {
                    this.switchResolution(resolution);
                }
            });
        });

        // Feature 1070: Double-click to reset zoom
        const canvas = document.getElementById('ohlc-chart');
        if (canvas) {
            canvas.addEventListener('dblclick', () => {
                this.resetZoom();
            });
        }
    }

    /**
     * Feature 1070: Reset chart zoom to default view
     */
    resetZoom() {
        if (this.chart) {
            this.chart.resetZoom();
            console.log('OHLC: Zoom reset to default');
        }
    }

    /**
     * Switch to a new resolution
     */
    async switchResolution(resolution) {
        if (resolution === this.currentResolution) return;

        console.log(`OHLC: Switching resolution ${this.currentResolution} -> ${resolution}`);

        this.currentResolution = resolution;
        this.saveResolutionPreference(resolution);
        this.updateSelectorUI();

        // Show loading state
        this.showLoading();

        // Fetch new data
        await this.loadData();

        // Notify listeners
        if (this.onResolutionChange) {
            this.onResolutionChange(resolution);
        }
    }

    /**
     * Switch to a new ticker
     */
    async switchTicker(ticker) {
        if (!ticker || ticker === this.currentTicker) return;

        ticker = ticker.toUpperCase().trim();
        console.log(`OHLC: Switching ticker ${this.currentTicker} -> ${ticker}`);

        this.currentTicker = ticker;
        this.updateSelectorUI();

        // Show loading state
        this.showLoading();

        // Fetch new data
        await this.loadData();

        // Notify listeners
        if (this.onTickerChange) {
            this.onTickerChange(ticker);
        }
    }

    /**
     * Show loading state on chart
     */
    showLoading() {
        this.isLoading = true;
        if (typeof showSkeleton === 'function') {
            showSkeleton('ohlcChart');
        }
    }

    /**
     * Hide loading state
     */
    hideLoading() {
        this.isLoading = false;
        if (typeof hideSkeleton === 'function') {
            hideSkeleton('ohlcChart');
        }
    }

    /**
     * Load OHLC data from API
     */
    async loadData() {
        try {
            const url = `${this.apiBaseUrl}${CONFIG.ENDPOINTS.OHLC}/${this.currentTicker}/ohlc?resolution=${this.currentResolution}&range=1M`;
            console.log(`OHLC: Fetching ${url}`);

            const response = await fetch(url, {
                headers: {
                    'Accept': 'application/json',
                    'X-User-ID': sessionUserId
                }
            });

            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error('Authentication required. Please refresh the page.');
                } else if (response.status === 404) {
                    throw new Error(`Ticker "${this.currentTicker}" not found.`);
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }

            const data = await response.json();

            // Check for resolution fallback
            if (data.resolution_fallback) {
                this.fallbackMessage = data.fallback_message || 'Intraday data not available. Showing daily data.';
                this.showFallbackMessage();
            } else {
                this.fallbackMessage = null;
                this.hideFallbackMessage();
            }

            // Update chart with candles
            this.updateChart(data.candles || []);
            this.lastError = null;

            // Hide loading
            this.hideLoading();

        } catch (error) {
            console.error('OHLC: Failed to load data:', error);
            this.lastError = error.message;
            this.updateChart([]);
            this.showError(error.message);
            this.hideLoading();
        }
    }

    /**
     * Show fallback message
     */
    showFallbackMessage() {
        const msgDiv = document.getElementById('ohlc-fallback-message');
        if (msgDiv) {
            msgDiv.textContent = this.fallbackMessage;
            msgDiv.style.display = 'block';
        }
    }

    /**
     * Hide fallback message
     */
    hideFallbackMessage() {
        const msgDiv = document.getElementById('ohlc-fallback-message');
        if (msgDiv) {
            msgDiv.style.display = 'none';
        }
    }

    /**
     * Show error message
     */
    showError(message) {
        const msgDiv = document.getElementById('ohlc-error-message');
        if (msgDiv) {
            msgDiv.textContent = message;
            msgDiv.style.display = 'block';
        }
    }

    /**
     * Hide error message
     */
    hideError() {
        const msgDiv = document.getElementById('ohlc-error-message');
        if (msgDiv) {
            msgDiv.style.display = 'none';
        }
    }

    /**
     * Initialize Chart.js chart with dual Y-axes (Feature 1065)
     */
    initChart() {
        const canvas = document.getElementById('ohlc-chart');
        if (!canvas) {
            console.warn('OHLC chart canvas not found');
            return;
        }

        // Feature 1077/1079: Register chartjs-plugin-zoom for pan/zoom functionality
        // Chart.js v4.x requires explicit plugin registration when loaded via CDN
        // Feature 1079: Use getPlugin() API instead of internal registry structure
        if (typeof ChartZoom !== 'undefined' && typeof Chart !== 'undefined') {
            // Check if plugin is already registered to avoid duplicate registration
            // Chart.js v4.x uses getPlugin() method - returns plugin or undefined
            const isRegistered = Chart.registry.getPlugin('zoom');
            if (!isRegistered) {
                Chart.register(ChartZoom);
                console.log('chartjs-plugin-zoom registered for pan/zoom functionality');
            }
        } else {
            console.warn('chartjs-plugin-zoom not available - pan/zoom disabled');
        }

        // Feature 1077: Set cursor style for pan interaction feedback
        canvas.style.cursor = 'grab';

        const ctx = canvas.getContext('2d');
        const overlayConfig = CONFIG.OVERLAY || {};

        // Create chart with OHLC bars and sentiment line overlay
        this.chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {
                        // Dataset 0: OHLC price bars
                        label: 'Price',
                        data: [],
                        backgroundColor: [],
                        borderColor: [],
                        borderWidth: 1,
                        barPercentage: 0.8,
                        yAxisID: 'price',
                        order: 2  // Render behind sentiment line
                    },
                    {
                        // Dataset 1: Sentiment overlay line (Feature 1065)
                        label: 'Sentiment',
                        data: [],
                        type: 'line',
                        borderColor: overlayConfig.sentimentColor || '#3b82f6',
                        backgroundColor: overlayConfig.sentimentColorBg || 'rgba(59, 130, 246, 0.15)',
                        borderWidth: overlayConfig.lineWidth || 2,
                        pointRadius: overlayConfig.pointRadius || 3,
                        pointBackgroundColor: overlayConfig.sentimentColor || '#3b82f6',
                        tension: 0.3,
                        fill: true,
                        yAxisID: 'sentiment',
                        order: 1  // Render on top of price bars
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    // Feature 1072: Hide legend for cleaner display
                    // Tooltip still shows Price and Sentiment values on hover
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            // Feature 1082/1083: Show full date+time in tooltip header
                            title: (items) => {
                                if (items.length > 0) {
                                    const item = items[0];
                                    // Get timestamp from numeric x value or dateStr
                                    const timestamp = item.raw.dateStr || new Date(item.raw.x).toISOString();
                                    const date = new Date(timestamp);
                                    // Full date+time format: "Mon 12/23 10:30"
                                    const weekday = date.toLocaleDateString('en-US', { weekday: 'short' });
                                    const month = date.getMonth() + 1;
                                    const day = date.getDate();
                                    const time = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
                                    return `${weekday} ${month}/${day} ${time}`;
                                }
                                return '';
                            },
                            label: (context) => {
                                // Handle OHLC dataset
                                if (context.datasetIndex === 0) {
                                    const candle = context.raw;
                                    if (candle && candle.ohlc) {
                                        return [
                                            `Open: $${candle.ohlc.open.toFixed(2)}`,
                                            `High: $${candle.ohlc.high.toFixed(2)}`,
                                            `Low: $${candle.ohlc.low.toFixed(2)}`,
                                            `Close: $${candle.ohlc.close.toFixed(2)}`
                                        ];
                                    }
                                }
                                // Handle sentiment dataset (Feature 1065)
                                if (context.datasetIndex === 1) {
                                    const value = context.raw;
                                    if (value !== null && value !== undefined) {
                                        const sign = value >= 0 ? '+' : '';
                                        return `Sentiment: ${sign}${value.toFixed(3)}`;
                                    }
                                    return 'Sentiment: N/A';
                                }
                                return '';
                            }
                        }
                    },
                    // Feature 1070: Vertical zoom for Price Chart
                    // Feature 1071: Horizontal pan for time navigation
                    // Allows mouse wheel zoom on Y-axis (price) centered around cursor
                    // Allows left-click-drag to pan along X-axis (time)
                    // Sentiment axis (right, -1 to 1) remains fixed
                    zoom: {
                        // Feature 1071: Pan configuration for horizontal navigation
                        pan: {
                            enabled: true,
                            mode: 'xy',          // Feature 1080: Allow both X (time) and Y (price) panning
                            threshold: 5,        // Minimum pan distance before action
                            modifierKey: null,   // No modifier key required (plain left-click)
                            // Feature 1077: Cursor feedback during pan
                            onPanStart: ({ chart }) => {
                                chart.canvas.style.cursor = 'grabbing';
                            },
                            onPanComplete: ({ chart }) => {
                                chart.canvas.style.cursor = 'grab';
                            }
                        },
                        zoom: {
                            wheel: {
                                enabled: true,
                                speed: 0.1
                            },
                            mode: 'y',
                            // Only zoom the price axis, not sentiment
                            scaleMode: 'y',
                            onZoom: ({ chart }) => {
                                // Restore sentiment axis to fixed -1 to 1 range
                                const sentimentScale = chart.scales.sentiment;
                                if (sentimentScale) {
                                    sentimentScale.options.min = overlayConfig.yAxisMin || -1.0;
                                    sentimentScale.options.max = overlayConfig.yAxisMax || 1.0;
                                }
                            }
                        },
                        // Feature 1073/1080: Fixed limits configuration with X-axis support
                        limits: {
                            x: {
                                min: 'original',  // Feature 1080: Use original data range for time axis
                                max: 'original',
                                minRange: 60000   // Minimum 1 minute visible (60 seconds * 1000ms)
                            },
                            price: {
                                min: 'original',  // Use data range, not $0 floor
                                minRange: 5       // Minimum $5 range when zoomed in
                            },
                            sentiment: {
                                min: -1,          // Fixed sentiment range
                                max: 1,
                                minRange: 2       // Full -1 to 1 range always
                            }
                        }
                    }
                },
                scales: {
                    // Feature 1082: Use time scale with numeric values for pan/zoom to work
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                minute: 'HH:mm',
                                hour: 'HH:mm',
                                day: 'MMM d'
                            }
                        },
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 0,
                            maxTicksLimit: 10,
                            // Feature 1082: Custom tick callback for formatted labels
                            callback: (value, index, ticks) => {
                                // The ohlcChart reference is set during initChart
                                if (this.chart && this.candles && this.candles.length > 0) {
                                    // Find the candle closest to this tick value
                                    const tickTime = new Date(value).getTime();
                                    const candleIndex = this.candles.findIndex(c =>
                                        new Date(c.date).getTime() === tickTime
                                    );
                                    if (candleIndex >= 0) {
                                        return this.formatTimestamp(this.candles[candleIndex].date, candleIndex, this.candles);
                                    }
                                }
                                // Fallback: use date-fns adapter default formatting
                                return new Date(value).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
                            }
                        }
                    },
                    // Left Y-axis: Price (Feature 1065: moved to left)
                    price: {
                        type: 'linear',
                        position: 'left',
                        grid: {
                            color: 'rgba(107, 114, 128, 0.2)'
                        },
                        ticks: {
                            callback: (value) => `$${value.toFixed(0)}`
                        },
                        title: {
                            display: true,
                            text: 'Price ($)'
                        }
                    },
                    // Right Y-axis: Sentiment (Feature 1065)
                    sentiment: {
                        type: 'linear',
                        position: 'right',
                        min: overlayConfig.yAxisMin || -1.0,
                        max: overlayConfig.yAxisMax || 1.0,
                        grid: {
                            display: false  // Don't duplicate gridlines
                        },
                        ticks: {
                            callback: (value) => value.toFixed(1)
                        },
                        title: {
                            display: true,
                            text: 'Sentiment'
                        }
                    }
                }
            }
        });
    }

    /**
     * Feature 1075: Calculate price limits from candle data
     * Returns min/max with 5% padding for visual clarity
     */
    calculatePriceLimits(candles) {
        if (!candles || candles.length === 0) {
            return { min: 0, max: 100 };  // Default for empty data
        }

        const lows = candles.map(c => c.low);
        const highs = candles.map(c => c.high);

        const dataMin = Math.min(...lows);
        const dataMax = Math.max(...highs);

        // Handle flat line (all same price) - add $0.50 buffer
        if (dataMin === dataMax) {
            return {
                min: dataMin - 0.5,
                max: dataMax + 0.5
            };
        }

        // Add 5% padding above and below
        const range = dataMax - dataMin;
        const padding = range * 0.05;

        return {
            min: dataMin - padding,
            max: dataMax + padding
        };
    }

    /**
     * Update chart with new candle data
     */
    updateChart(candles) {
        if (!this.chart) return;

        this.hideError();

        // Store raw candles for sentiment alignment (Feature 1065)
        this.ohlcCandles = candles || [];

        if (!candles || candles.length === 0) {
            this.chart.data.labels = [];
            this.chart.data.datasets[0].data = [];
            this.chart.data.datasets[1].data = [];  // Clear sentiment too
            this.chart.update('none');
            return;
        }

        // Feature 1082: Store candles for tick callback access
        this.candles = candles;

        // Feature 1082: Use numeric epoch milliseconds for X-axis (enables pan/zoom)
        // Labels are now auto-generated by time scale, tick callback formats them
        const labels = candles.map(c => new Date(c.date).getTime());

        // Create data for floating bar chart (simulating candlesticks)
        // Feature 1082: Use numeric x values instead of formatted strings
        const data = candles.map((c, i) => ({
            x: new Date(c.date).getTime(),  // Numeric epoch ms for pan calculations
            y: [c.low, c.high],  // Bar spans from low to high
            ohlc: { open: c.open, high: c.high, low: c.low, close: c.close },
            dateStr: c.date  // Keep original for tooltip formatting
        }));

        // Determine colors based on price movement
        const colors = candles.map(c =>
            c.close >= c.open ? CONFIG.OHLC_COLORS.bullish : CONFIG.OHLC_COLORS.bearish
        );

        this.chart.data.labels = labels;
        this.chart.data.datasets[0].data = data;
        this.chart.data.datasets[0].backgroundColor = colors;
        this.chart.data.datasets[0].borderColor = colors;

        // Update sentiment overlay if we have data (Feature 1065)
        this.updateSentimentOverlay();

        // Feature 1075: Calculate dynamic price limits from actual data
        // This fixes the issue where 'original' keyword preserves stale initial values
        const priceLimits = this.calculatePriceLimits(candles);
        this.chart.options.plugins.zoom.limits.price.min = priceLimits.min;
        this.chart.options.plugins.zoom.limits.price.max = priceLimits.max;

        // Feature 1082: Set numeric X-axis limits for pan boundaries
        const xMin = data[0].x;
        const xMax = data[data.length - 1].x;
        this.chart.options.plugins.zoom.limits.x.min = xMin;
        this.chart.options.plugins.zoom.limits.x.max = xMax;

        // Also set the scale min/max so Chart.js respects data range
        this.chart.options.scales.price.min = priceLimits.min;
        this.chart.options.scales.price.max = priceLimits.max;
        this.chart.options.scales.x.min = xMin;
        this.chart.options.scales.x.max = xMax;

        // Apply config changes before resetZoom
        this.chart.update('none');

        // Feature 1072: Reset zoom to show all new data (auto-fit on load/resolution change)
        this.chart.resetZoom();

        console.log(`OHLC: Updated chart with ${candles.length} candles, price range $${priceLimits.min.toFixed(2)}-$${priceLimits.max.toFixed(2)}`);
    }

    /**
     * Feature 1065: Load sentiment data from timeseries API
     * @param {string} resolution - Sentiment resolution (e.g., '1h', '5m')
     */
    async loadSentimentData(resolution) {
        if (!CONFIG.OVERLAY?.enabled) {
            console.log('OHLC: Sentiment overlay disabled');
            return;
        }

        this.sentimentResolution = resolution;

        try {
            const url = `${this.apiBaseUrl}${CONFIG.ENDPOINTS.TIMESERIES}/${this.currentTicker}?resolution=${resolution}`;
            console.log(`OHLC: Fetching sentiment overlay ${url}`);

            const response = await fetch(url, {
                headers: {
                    'Accept': 'application/json',
                    'X-User-ID': sessionUserId
                }
            });

            if (!response.ok) {
                console.warn(`OHLC: Sentiment fetch failed: ${response.status}`);
                this.sentimentData = [];
                this.updateSentimentOverlay();
                return;
            }

            const data = await response.json();
            this.sentimentData = data.buckets || [];

            console.log(`OHLC: Loaded ${this.sentimentData.length} sentiment buckets`);

            // Update the overlay on the chart
            this.updateSentimentOverlay();

        } catch (error) {
            console.error('OHLC: Failed to load sentiment data:', error);
            this.sentimentData = [];
            this.updateSentimentOverlay();
        }
    }

    /**
     * Feature 1065: Update sentiment line overlay on chart
     * Aligns sentiment data with OHLC candle timestamps
     */
    updateSentimentOverlay() {
        if (!this.chart || !this.chart.data.datasets[1]) return;

        // If no sentiment data, clear the overlay
        if (!this.sentimentData || this.sentimentData.length === 0) {
            this.chart.data.datasets[1].data = [];
            return;
        }

        // Build a map of sentiment by timestamp for alignment
        const sentimentByTime = new Map();
        this.sentimentData.forEach(bucket => {
            // Feature 1069: Fix field name - API returns 'timestamp', not 'bucket_timestamp' or 'SK'
            const ts = bucket.timestamp || bucket.bucket_timestamp || bucket.SK;
            if (ts) {
                // Parse and normalize to date string for matching
                const date = new Date(ts);
                const normalized = date.toISOString();
                sentimentByTime.set(normalized, bucket.avg !== undefined ? bucket.avg : (bucket.sum / bucket.count) || 0);
            }
        });

        // Align sentiment values to OHLC candle timestamps
        // Feature 1082: Use {x, y} format with numeric x for time scale compatibility
        const alignedSentiment = this.ohlcCandles.map(candle => {
            const candleDate = new Date(candle.date);
            const candleTime = candleDate.getTime();

            // Try exact match first
            const exactKey = candleDate.toISOString();
            if (sentimentByTime.has(exactKey)) {
                return { x: candleTime, y: sentimentByTime.get(exactKey) };
            }

            // Find nearest sentiment bucket within 1 hour
            let nearestValue = null;
            let nearestDelta = Infinity;

            for (const [ts, value] of sentimentByTime.entries()) {
                const sentimentTime = new Date(ts).getTime();
                const delta = Math.abs(candleTime - sentimentTime);
                if (delta < nearestDelta && delta < 3600000) {  // Within 1 hour
                    nearestDelta = delta;
                    nearestValue = value;
                }
            }

            // Return null as y value if no match (line will have gap)
            return { x: candleTime, y: nearestValue };
        });

        this.chart.data.datasets[1].data = alignedSentiment;
        console.log(`OHLC: Updated sentiment overlay with ${alignedSentiment.filter(v => v.y !== null).length} aligned points`);
    }

    /**
     * Format timestamp for chart label with day context (Feature 1081)
     * @param {string} timestamp - ISO timestamp
     * @param {number} index - Candle index in data array (optional)
     * @param {Array} candles - All candles for day boundary detection (optional)
     */
    formatTimestamp(timestamp, index = 0, candles = null) {
        const date = new Date(timestamp);
        const resolution = this.currentResolution;

        if (resolution === 'D') {
            // Day resolution: "Dec 23" format
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }

        // Feature 1081: Check if this is first candle of a new day for multi-day data
        if (candles && candles.length > 1) {
            const isFirstOfDay = index === 0 || this.isDifferentDay(candles[index - 1].date, timestamp);

            if (isFirstOfDay) {
                // Show abbreviated date: "Mon 12/23"
                const weekday = date.toLocaleDateString('en-US', { weekday: 'short' });
                const monthDay = `${date.getMonth() + 1}/${date.getDate()}`;
                return `${weekday} ${monthDay}`;
            }
        }

        // Same day or no context: show time only
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    }

    /**
     * Check if two timestamps are on different calendar days (Feature 1081)
     */
    isDifferentDay(timestamp1, timestamp2) {
        const d1 = new Date(timestamp1);
        const d2 = new Date(timestamp2);
        return d1.toDateString() !== d2.toDateString();
    }
}

// Export for global access
window.OHLCChart = OHLCChart;

// Global instance (initialized after session auth in app.js)
let ohlcChartInstance = null;

/**
 * Initialize OHLC chart (called from app.js after session init)
 */
async function initOHLCChart(ticker = 'AAPL') {
    if (ohlcChartInstance) {
        console.log('OHLC chart already initialized');
        return ohlcChartInstance;
    }

    ohlcChartInstance = new OHLCChart({
        ticker: ticker,
        onTickerChange: (ticker) => {
            console.log(`OHLC ticker changed to: ${ticker}`);
        },
        onResolutionChange: (resolution) => {
            console.log(`OHLC resolution changed to: ${resolution}`);
        }
    });

    await ohlcChartInstance.init();
    return ohlcChartInstance;
}

/**
 * Update OHLC chart ticker (called when user changes ticker input)
 */
async function updateOHLCTicker(ticker) {
    if (ohlcChartInstance) {
        await ohlcChartInstance.switchTicker(ticker);
    }
}

/**
 * Set OHLC chart resolution (Feature 1064: unified resolution selector)
 * Called from unified-resolution.js to update OHLC chart resolution
 * @param {string} resolution - OHLC resolution value ('1', '5', '15', '30', '60', 'D')
 * @param {boolean} isFallback - True if this is a fallback from a different unified resolution
 * @param {string} sentimentResolution - Optional sentiment resolution to load for overlay (Feature 1065)
 */
async function setOHLCResolution(resolution, isFallback = false, sentimentResolution = null) {
    if (!ohlcChartInstance) {
        console.warn('OHLC chart not initialized');
        return;
    }

    // Skip if already at this resolution
    if (ohlcChartInstance.currentResolution === resolution) {
        // Still load sentiment if provided (Feature 1065)
        if (sentimentResolution) {
            await ohlcChartInstance.loadSentimentData(sentimentResolution);
        }
        return;
    }

    console.log(`OHLC: External resolution set to ${resolution}${isFallback ? ' (fallback)' : ''}`);

    ohlcChartInstance.currentResolution = resolution;
    ohlcChartInstance.showLoading();
    await ohlcChartInstance.loadData();

    // Feature 1065: Load sentiment overlay data if resolution provided
    if (sentimentResolution) {
        await ohlcChartInstance.loadSentimentData(sentimentResolution);
    }

    // Show fallback indicator if needed
    if (isFallback) {
        ohlcChartInstance.fallbackMessage = 'Resolution mapped from unified selector';
        ohlcChartInstance.showFallbackMessage();
    }
}

/**
 * Feature 1065: Load sentiment overlay for OHLC chart
 * Called from unified-resolution.js to update sentiment overlay
 * @param {string} sentimentResolution - Sentiment resolution (e.g., '1h', '5m')
 */
async function loadOHLCSentimentOverlay(sentimentResolution) {
    if (!ohlcChartInstance) {
        console.warn('OHLC chart not initialized');
        return;
    }
    await ohlcChartInstance.loadSentimentData(sentimentResolution);
}

/**
 * Hide the local OHLC resolution selector (Feature 1064)
 * Called when unified resolution selector is active
 */
function hideOHLCResolutionSelector() {
    const container = document.getElementById('ohlc-resolution-selector');
    if (container) {
        container.style.display = 'none';
    }
}

// Export functions for external use
window.setOHLCResolution = setOHLCResolution;
window.hideOHLCResolutionSelector = hideOHLCResolutionSelector;
window.loadOHLCSentimentOverlay = loadOHLCSentimentOverlay;  // Feature 1065
window.initOHLCChart = initOHLCChart;  // Feature 1066: Fix missing export
window.updateOHLCTicker = updateOHLCTicker;  // Feature 1066: Fix missing export
