/**
 * OHLC Chart Module (Feature 1057)
 * ================================
 *
 * Displays OHLC candlestick price data with time resolution selector.
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
     * Bind event handlers for resolution buttons
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
     * Initialize Chart.js chart
     */
    initChart() {
        const canvas = document.getElementById('ohlc-chart');
        if (!canvas) {
            console.warn('OHLC chart canvas not found');
            return;
        }

        const ctx = canvas.getContext('2d');

        // Create line chart (Chart.js doesn't have native candlestick)
        // We'll use a bar chart with custom styling to simulate candlesticks
        this.chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Price Range',
                        data: [],
                        backgroundColor: [],
                        borderColor: [],
                        borderWidth: 1,
                        barPercentage: 0.8
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const candle = context.raw;
                                if (candle && candle.ohlc) {
                                    return [
                                        `Open: $${candle.ohlc.open.toFixed(2)}`,
                                        `High: $${candle.ohlc.high.toFixed(2)}`,
                                        `Low: $${candle.ohlc.low.toFixed(2)}`,
                                        `Close: $${candle.ohlc.close.toFixed(2)}`
                                    ];
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 0,
                            maxTicksLimit: 10
                        }
                    },
                    y: {
                        position: 'right',
                        grid: {
                            color: 'rgba(107, 114, 128, 0.2)'
                        },
                        ticks: {
                            callback: (value) => `$${value.toFixed(0)}`
                        }
                    }
                }
            }
        });
    }

    /**
     * Update chart with new candle data
     */
    updateChart(candles) {
        if (!this.chart) return;

        this.hideError();

        if (!candles || candles.length === 0) {
            this.chart.data.labels = [];
            this.chart.data.datasets[0].data = [];
            this.chart.update('none');
            return;
        }

        // Format labels based on resolution
        // Note: Backend returns 'date' field, not 'timestamp'
        const labels = candles.map(c => this.formatTimestamp(c.date));

        // Create data for floating bar chart (simulating candlesticks)
        const data = candles.map(c => ({
            x: this.formatTimestamp(c.date),
            y: [c.low, c.high],  // Bar spans from low to high
            ohlc: { open: c.open, high: c.high, low: c.low, close: c.close }
        }));

        // Determine colors based on price movement
        const colors = candles.map(c =>
            c.close >= c.open ? CONFIG.OHLC_COLORS.bullish : CONFIG.OHLC_COLORS.bearish
        );

        this.chart.data.labels = labels;
        this.chart.data.datasets[0].data = data;
        this.chart.data.datasets[0].backgroundColor = colors;
        this.chart.data.datasets[0].borderColor = colors;

        this.chart.update('none');

        console.log(`OHLC: Updated chart with ${candles.length} candles`);
    }

    /**
     * Format timestamp for chart label
     */
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const resolution = this.currentResolution;

        if (resolution === 'D') {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        } else {
            return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
        }
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
