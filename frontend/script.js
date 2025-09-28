// Main JavaScript file for Flood Dashboard
class FloodDashboard {
    constructor() {
        this.charts = {};
        this.updateIntervals = {};
        this.retryCounters = {};
        
        // Initialize dashboard when DOM is loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    async init() {
        try {
            console.log('Initializing Flood Dashboard...');
            
            // Setup error handling
            this.setupErrorHandling();
            
            // Setup UI event listeners
            this.setupEventListeners();

            // Initialize all components
            await this.loadAllData();
            
            // Setup auto-refresh if enabled
            if (CONFIG.UI.autoRefresh) {
                this.setupAutoRefresh();
            }
            
            // Setup map
            this.setupMap();
            
            // Hide loading overlay
            this.hideLoadingOverlay();
            
            console.log('Flood Dashboard initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize dashboard:', error);
            this.showError('Failed to initialize dashboard', error.message);
        }
    }

    setupEventListeners() {
        // Future UI event listeners can go here
    }

    // API Methods
    async apiRequest(endpoint, options = {}) {
        const url = getApiUrl(endpoint);
        const controller = new AbortController();
        
        // Set timeout
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.API.TIMEOUT);
        
        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
            
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }
            
            throw error;
        }
    }

    async getData(endpoint, fallbackData = null) {
        const retryKey = endpoint;
        
        try {
            // Use mock data if enabled
            if (CONFIG.MOCK_DATA.enabled) {
                console.log(`Using mock data for ${endpoint}`);
                await this.simulateDelay(500); // Simulate network delay
                return CONFIG.MOCK_DATA.data[endpoint] || fallbackData;
            }
            
            const data = await this.apiRequest(endpoint);
            this.retryCounters[retryKey] = 0; // Reset retry counter on success
            return data;
            
        } catch (error) {
            console.warn(`API request failed for ${endpoint}:`, error.message);
            
            // Implement retry logic
            const retryCount = this.retryCounters[retryKey] || 0;
            if (retryCount < CONFIG.API.RETRY_ATTEMPTS) {
                this.retryCounters[retryKey] = retryCount + 1;
                console.log(`Retrying ${endpoint} (attempt ${retryCount + 1}/${CONFIG.API.RETRY_ATTEMPTS})`);
                
                await this.simulateDelay(CONFIG.API.RETRY_DELAY);
                return this.getData(endpoint, fallbackData);
            }
            
            // If all retries failed and fallback is enabled, use mock data
            if (CONFIG.ERROR_HANDLING.fallbackToMockData && CONFIG.MOCK_DATA.data[endpoint]) {
                console.log(`Using fallback mock data for ${endpoint}`);
                return CONFIG.MOCK_DATA.data[endpoint];
            }
            
            throw error;
        }
    }

    // Data Loading Methods
    async loadAllData() {
        const loadingTasks = [
            this.loadFloodRisk(),
            this.loadRiverLevel(),
            this.loadRainForecast(),
            this.loadRiverForecast(),
            this.loadRiverHistory(),
            this.loadRainfallComparison(),
            this.updateSystemStatus()
        ];

        // Execute all loading tasks in parallel
        await Promise.allSettled(loadingTasks);
    }

    async loadFloodRisk() {
        try {
            const data = await this.getData('currentFloodRisk');
            this.updateFloodRiskDisplay(data);
        } catch (error) {
            console.error('Failed to load flood risk data:', error);
            this.showElementError('flood-risk-content', 'Unable to load flood risk data');
        }
    }

    async loadRiverLevel() {
        try {
            const data = await this.getData('riverLevel');
            this.updateRiverLevelDisplay(data);
        } catch (error) {
            console.error('Failed to load river level data:', error);
            this.showElementError('river-level-content', 'Unable to load river level data');
        }
    }

    async loadRainForecast() {
        try {
            const data = await this.getData('forecastRain');
            this.createRainForecastChart(data);
        } catch (error) {
            console.error('Failed to load rain forecast:', error);
            this.showChartError('rain-forecast-chart', 'Unable to load rain forecast');
        }
    }

    async loadRiverForecast() {
        try {
            const data = await this.getData('forecastRiver');
            this.createRiverForecastChart(data);
        } catch (error) {
            console.error('Failed to load river forecast:', error);
            this.showChartError('river-forecast-chart', 'Unable to load river forecast');
        }
    }

    async loadRiverHistory() {
        try {
            const data = await this.getData('historyRiver');
            this.createRiverHistoryChart(data);
        } catch (error) {
            console.error('Failed to load river history:', error);
            this.showChartError('river-history-chart', 'Unable to load river history');
        }
    }

    async loadRainfallComparison() {
        try {
            const data = await this.getData('rainfallComparison');
            this.createRainfallComparisonChart(data);
        } catch (error) {
            console.error('Failed to load rainfall comparison:', error);
            this.showChartError('rainfall-comparison-chart', 'Unable to load rainfall comparison');
        }
    }

    // Display Update Methods
    updateFloodRiskDisplay(data) {
        const container = document.getElementById('flood-risk-content');
        if (!container) return;

        const riskConfig = getRiskConfig(data.level);
        
        container.innerHTML = `
            <div class="flood-risk-status ${data.level}" style="color: ${riskConfig.color}; background-color: ${riskConfig.bgColor}; border-color: ${riskConfig.borderColor};">
                <i class="${riskConfig.icon}"></i>
                ${data.status}
            </div>
            ${data.confidence ? `<div class="text-sm text-gray-600 mt-2">Confidence: ${data.confidence}%</div>` : ''}
        `;
        
        container.classList.add('fade-in');
    }

    updateRiverLevelDisplay(data) {
        const container = document.getElementById('river-level-content');
        if (!container) return;

        container.innerHTML = `
            <div class="river-level-info">
                <div class="river-location">
                    <i class="fas fa-map-marker-alt"></i>
                    ${data.riverName} - ${data.stationName}
                </div>
                <div class="river-level-value">
                    ${data.currentLevel} ${data.unit}
                </div>
                ${data.normalLevel ? `<div class="text-xs text-gray-500 mt-1">Normal: ${data.normalLevel}${data.unit} | Danger: ${data.dangerLevel}${data.unit}</div>` : ''}
            </div>
        `;
        
        container.classList.add('fade-in');
    }

    updateSystemStatus() {
        const lastUpdateElement = document.getElementById('last-update');
        if (lastUpdateElement) {
            const now = new Date();
            const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            lastUpdateElement.textContent = `Updated ${timeString}`;
        }
    }

    // Chart Creation Methods
    createRainForecastChart(data) {
        const ctx = document.getElementById('rain-forecast-chart');
        if (!ctx) return;

        if (this.charts.rainForecast) {
            this.charts.rainForecast.destroy();
        }

        this.charts.rainForecast = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => item.day),
                datasets: [{
                    label: 'Rainfall (mm)',
                    data: data.map(item => item.rainfall),
                    borderColor: CONFIG.CHARTS.colors.rainfall,
                    backgroundColor: CONFIG.CHARTS.colors.rainfall + '20',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: CONFIG.CHARTS.colors.rainfall,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 6
                }]
            },
            options: {
                ...CONFIG.CHARTS.common,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Rainfall (mm)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Days'
                        }
                    }
                },
                plugins: {
                    ...CONFIG.CHARTS.common.plugins,
                    tooltip: {
                        ...CONFIG.CHARTS.common.plugins.tooltip,
                        callbacks: {
                            afterLabel: function(context) {
                                const dataItem = data[context.dataIndex];
                                return dataItem.probability ? `Probability: ${dataItem.probability}%` : '';
                            }
                        }
                    }
                }
            }
        });
    }

    createRiverForecastChart(data) {
        const ctx = document.getElementById('river-forecast-chart');
        if (!ctx) return;

        if (this.charts.riverForecast) {
            this.charts.riverForecast.destroy();
        }

        this.charts.riverForecast = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => item.day),
                datasets: [{
                    label: 'River Level (m)',
                    data: data.map(item => item.level),
                    borderColor: CONFIG.CHARTS.colors.riverLevel,
                    backgroundColor: CONFIG.CHARTS.colors.riverLevel + '20',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: CONFIG.CHARTS.colors.riverLevel,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 6
                }]
            },
            options: {
                ...CONFIG.CHARTS.common,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Water Level (m)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Days'
                        }
                    }
                }
            }
        });
    }

    createRiverHistoryChart(data) {
        const ctx = document.getElementById('river-history-chart');
        if (!ctx) return;

        if (this.charts.riverHistory) {
            this.charts.riverHistory.destroy();
        }

        this.charts.riverHistory = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => `Day ${item.day}`),
                datasets: [{
                    label: 'River Level (m)',
                    data: data.map(item => item.level),
                    borderColor: CONFIG.CHARTS.colors.riverHistory,
                    backgroundColor: CONFIG.CHARTS.colors.riverHistory + '10',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: CONFIG.CHARTS.colors.riverHistory,
                    pointHoverBorderColor: '#fff',
                    pointHoverBorderWidth: 2
                }]
            },
            options: {
                ...CONFIG.CHARTS.common,
                scales: {
                    y: {
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: 'Water Level (m)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Last 30 Days'
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }

    createRainfallComparisonChart(data) {
        const ctx = document.getElementById('rainfall-comparison-chart');
        if (!ctx) return;

        if (this.charts.rainfallComparison) {
            this.charts.rainfallComparison.destroy();
        }

        this.charts.rainfallComparison = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.month),
                datasets: [{
                    label: 'Rainfall (mm)',
                    data: data.map(item => item.rainfall),
                    backgroundColor: [
                        CONFIG.CHARTS.colors.comparison,
                        CONFIG.CHARTS.colors.comparison + '80'
                    ],
                    borderColor: CONFIG.CHARTS.colors.comparison,
                    borderWidth: 2,
                    borderRadius: 8,
                    borderSkipped: false
                }]
            },
            options: {
                ...CONFIG.CHARTS.common,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Rainfall (mm)'
                        }
                    }
                },
                plugins: {
                    ...CONFIG.CHARTS.common.plugins,
                    tooltip: {
                        ...CONFIG.CHARTS.common.plugins.tooltip,
                        callbacks: {
                            afterLabel: function(context) {
                                const dataItem = data[context.dataIndex];
                                return dataItem.days ? `Days: ${dataItem.days}` : '';
                            }
                        }
                    }
                }
            }
        });
    }

    // Map Setup
    setupMap() {
        const mapIframe = document.getElementById('flood-map');
        const mapLoading = document.getElementById('map-loading');
        const mapFallback = document.getElementById('map-fallback');
        const mapEndpoint = document.getElementById('map-endpoint');

        if (mapEndpoint) {
            mapEndpoint.textContent = `Connected to: ${getApiUrl('map')}`;
        }

        if (CONFIG.MOCK_DATA.enabled) {
            // Show fallback for mock mode
            if (mapLoading) mapLoading.style.display = 'none';
            if (mapFallback) mapFallback.style.display = 'flex';
            return;
        }

        // Setup real map
        if (mapIframe) {
            mapIframe.src = getApiUrl('map') + '?t=' + new Date().getTime();
            
            mapIframe.onload = () => {
                if (mapLoading) mapLoading.style.display = 'none';
            };
            
            mapIframe.onerror = () => {
                if (mapLoading) mapLoading.style.display = 'none';
                if (mapFallback) mapFallback.style.display = 'flex';
            };
        }
    }

    // Auto-refresh Setup
    setupAutoRefresh() {
        // Set up individual refresh intervals
        this.updateIntervals.floodRisk = setInterval(() => {
            this.loadFloodRisk();
        }, CONFIG.UPDATE_INTERVALS.floodRisk);

        this.updateIntervals.riverLevel = setInterval(() => {
            this.loadRiverLevel();
        }, CONFIG.UPDATE_INTERVALS.riverLevel);

        this.updateIntervals.forecasts = setInterval(() => {
            this.loadRainForecast();
            this.loadRiverForecast();
        }, CONFIG.UPDATE_INTERVALS.forecasts);

        this.updateIntervals.history = setInterval(() => {
            this.loadRiverHistory();
            this.loadRainfallComparison();
        }, CONFIG.UPDATE_INTERVALS.history);

        this.updateIntervals.systemStatus = setInterval(() => {
            this.updateSystemStatus();
        }, CONFIG.UPDATE_INTERVALS.systemStatus);

        console.log('Auto-refresh enabled for all components');
    }

    // Error Handling
    setupErrorHandling() {
        const retryBtn = document.getElementById('retry-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                this.hideErrorModal();
                this.loadAllData();
            });
        }

        // Global error handler
        window.addEventListener('error', (event) => {
            console.error('Global error:', event.error);
            if (CONFIG.UI.debug) {
                this.showError('JavaScript Error', event.error.message);
            }
        });

        // Unhandled promise rejection handler
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            if (CONFIG.UI.debug) {
                this.showError('Promise Rejection', event.reason.message || 'Unknown error');
            }
        });
    }

    showError(title, message) {
        const errorModal = document.getElementById('error-modal');
        const errorMessage = document.getElementById('error-message');
        
        if (errorModal && errorMessage) {
            errorMessage.textContent = message;
            errorModal.classList.add('show');
        }
        
        console.error(`${title}: ${message}`);
    }

    hideErrorModal() {
        const errorModal = document.getElementById('error-modal');
        if (errorModal) {
            errorModal.classList.remove('show');
        }
    }

    showElementError(elementId, message) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = `
                <div class="text-center text-red-500 py-4">
                    <i class="fas fa-exclamation-triangle mb-2"></i>
                    <p class="text-sm">${message}</p>
                </div>
            `;
        }
    }

    showChartError(canvasId, message) {
        const canvas = document.getElementById(canvasId);
        if (canvas) {
            const container = canvas.parentElement;
            container.innerHTML = `
                <div class="chart-loading">
                    <div class="text-center text-red-500">
                        <i class="fas fa-chart-line text-2xl mb-2"></i>
                        <p class="text-sm">${message}</p>
                    </div>
                </div>
            `;
        }
    }

    hideLoadingOverlay() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => {
                overlay.style.display = 'none';
            }, CONFIG.UI.animations.loading);
        }
    }

    // Utility Methods
    async simulateDelay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    destroy() {
        // Clean up intervals
        Object.values(this.updateIntervals).forEach(interval => {
            clearInterval(interval);
        });

        // Destroy charts
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });

        console.log('Dashboard destroyed');
    }
}

// Initialize dashboard when script loads
const dashboard = new FloodDashboard();

// Export for potential external use
if (typeof window !== 'undefined') {
    window.FloodDashboard = FloodDashboard;
    window.dashboard = dashboard;
}

// Handle page visibility changes to pause/resume updates
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('Page hidden, pausing updates');
        // Could pause intervals here if needed
    } else {
        console.log('Page visible, resuming updates');
        // Could resume intervals here if needed
        dashboard.updateSystemStatus();
    }
});
