/**
 * Unified Resolution Selector (Feature 1064)
 * ==========================================
 *
 * Single resolution selector that controls both OHLC price chart and sentiment
 * trend chart. Uses resolution mapping to handle different supported values
 * between the two chart types.
 *
 * Dependencies:
 *   - config.js: CONFIG.UNIFIED_RESOLUTIONS, CONFIG.DEFAULT_UNIFIED_RESOLUTION
 *   - ohlc.js: ohlcChartInstance.setResolution()
 *   - timeseries.js: timeseriesChartInstance.setResolution()
 */

/**
 * UnifiedResolutionSelector class
 * Manages the unified resolution control and coordinates updates to both charts
 */
class UnifiedResolutionSelector {
    constructor() {
        this.currentResolution = null;
        this.containerEl = null;
        this.onOhlcChange = null;  // Callback for OHLC chart
        this.onSentimentChange = null;  // Callback for sentiment chart
    }

    /**
     * Initialize the unified resolution selector
     * @param {Object} options - Configuration options
     * @param {Function} options.onOhlcChange - Callback when OHLC resolution changes
     * @param {Function} options.onSentimentChange - Callback when sentiment resolution changes
     * @param {string} options.containerId - DOM element ID for the selector
     */
    init(options = {}) {
        this.onOhlcChange = options.onOhlcChange || null;
        this.onSentimentChange = options.onSentimentChange || null;

        const containerId = options.containerId || 'unified-resolution-selector';
        this.containerEl = document.getElementById(containerId);

        if (!this.containerEl) {
            console.warn(`UnifiedResolutionSelector: Container #${containerId} not found`);
            return;
        }

        // Load saved resolution or use default
        this.currentResolution = this.loadResolution();

        // Render the selector
        this.render();

        // Bind events
        this.bindEvents();

        // Apply initial resolution to both charts
        this.applyResolution(this.currentResolution);

        console.log(`UnifiedResolutionSelector: Initialized with resolution ${this.currentResolution}`);
    }

    /**
     * Load resolution from sessionStorage or return default
     */
    loadResolution() {
        const saved = sessionStorage.getItem(CONFIG.UNIFIED_RESOLUTION_KEY);
        if (saved && CONFIG.UNIFIED_RESOLUTIONS.find(r => r.key === saved)) {
            return saved;
        }
        return CONFIG.DEFAULT_UNIFIED_RESOLUTION;
    }

    /**
     * Save resolution to sessionStorage
     */
    saveResolution(resolution) {
        sessionStorage.setItem(CONFIG.UNIFIED_RESOLUTION_KEY, resolution);
    }

    /**
     * Render the resolution selector buttons
     */
    render() {
        const buttons = CONFIG.UNIFIED_RESOLUTIONS.map(res => {
            const isActive = res.key === this.currentResolution;
            const exactClass = res.exact ? '' : 'has-fallback';
            return `
                <button
                    class="unified-resolution-btn ${isActive ? 'active' : ''} ${exactClass}"
                    data-resolution="${res.key}"
                    data-ohlc="${res.ohlc}"
                    data-sentiment="${res.sentiment}"
                    aria-pressed="${isActive}"
                    title="${res.exact ? res.label : `${res.label} (mapped: OHLC=${res.ohlc}, Sentiment=${res.sentiment})`}"
                >
                    ${res.label}
                    ${!res.exact ? '<span class="fallback-dot" aria-hidden="true"></span>' : ''}
                </button>
            `;
        }).join('');

        this.containerEl.innerHTML = `
            <div class="unified-resolution-group" role="group" aria-label="Time resolution selector">
                <span class="unified-resolution-label">Resolution:</span>
                ${buttons}
            </div>
        `;
    }

    /**
     * Bind click events to resolution buttons
     */
    bindEvents() {
        this.containerEl.addEventListener('click', (e) => {
            const btn = e.target.closest('.unified-resolution-btn');
            if (!btn) return;

            const resolution = btn.dataset.resolution;
            if (resolution && resolution !== this.currentResolution) {
                this.switchResolution(resolution);
            }
        });
    }

    /**
     * Switch to a new resolution
     */
    switchResolution(resolution) {
        const resConfig = CONFIG.UNIFIED_RESOLUTIONS.find(r => r.key === resolution);
        if (!resConfig) {
            console.warn(`UnifiedResolutionSelector: Unknown resolution ${resolution}`);
            return;
        }

        this.currentResolution = resolution;
        this.saveResolution(resolution);

        // Update UI
        this.updateActiveButton(resolution);

        // Apply to both charts
        this.applyResolution(resolution);

        console.log(`UnifiedResolutionSelector: Switched to ${resolution}`);
    }

    /**
     * Update active button state in UI
     */
    updateActiveButton(resolution) {
        const buttons = this.containerEl.querySelectorAll('.unified-resolution-btn');
        buttons.forEach(btn => {
            const isActive = btn.dataset.resolution === resolution;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive);
        });
    }

    /**
     * Apply resolution to both charts via callbacks
     */
    applyResolution(resolution) {
        const resConfig = CONFIG.UNIFIED_RESOLUTIONS.find(r => r.key === resolution);
        if (!resConfig) return;

        // Notify OHLC chart
        if (this.onOhlcChange) {
            this.onOhlcChange(resConfig.ohlc, !resConfig.exact);
        }

        // Notify sentiment chart
        if (this.onSentimentChange) {
            this.onSentimentChange(resConfig.sentiment, !resConfig.exact);
        }
    }

    /**
     * Get current resolution config
     */
    getCurrentResolution() {
        return CONFIG.UNIFIED_RESOLUTIONS.find(r => r.key === this.currentResolution);
    }
}

// Global instance
let unifiedResolutionInstance = null;

/**
 * Initialize the unified resolution selector
 * Called from app.js after charts are ready
 */
function initUnifiedResolution(options) {
    unifiedResolutionInstance = new UnifiedResolutionSelector();
    unifiedResolutionInstance.init(options);
    return unifiedResolutionInstance;
}

/**
 * Get the current unified resolution
 */
function getUnifiedResolution() {
    if (!unifiedResolutionInstance) return null;
    return unifiedResolutionInstance.getCurrentResolution();
}

// Export for use by other modules
window.initUnifiedResolution = initUnifiedResolution;
window.getUnifiedResolution = getUnifiedResolution;
