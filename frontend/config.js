// Configuration file for Flood Dashboard
// Modify these settings to match your environment

const CONFIG = {
    // API Configuration
    API: {
        BASE_URL: 'http://127.0.0.1:5000',
        ENDPOINTS: {
            currentFloodRisk: '/api/current_flood_risk',
            riverLevel: '/api/river_level',
            forecastRain: '/api/forecast_rain',
            forecastRiver: '/api/forecast_river',
            historyRiver: '/api/history_river',
            rainfallComparison: '/api/rainfall_comparison',
            map: '/api/map'
        },
        // Request timeout in milliseconds
        TIMEOUT: 10000,
        // Retry attempts for failed requests
        RETRY_ATTEMPTS: 3,
        // Retry delay in milliseconds
        RETRY_DELAY: 2000
    },

    // Update intervals (in milliseconds)
    UPDATE_INTERVALS: {
        floodRisk: 30000,      // 30 seconds
        riverLevel: 60000,     // 1 minute
        forecasts: 300000,     // 5 minutes
        history: 600000,       // 10 minutes
        systemStatus: 30000    // 30 seconds
    },

    // Chart Configuration
    CHARTS: {
        // Common chart options
        common: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#3b82f6',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                }
            }
        },
        
        // Specific chart colors
        colors: {
            rainfall: '#3b82f6',        // Blue
            riverLevel: '#10b981',      // Green
            riverHistory: '#8b5cf6',    // Purple
            comparison: '#f59e0b'       // Amber
        }
    },

    // Risk Level Configuration
    RISK_LEVELS: {
        low: {
            color: '#10b981',
            bgColor: '#ecfdf5',
            borderColor: '#d1fae5',
            icon: 'fas fa-check-circle'
        },
        moderate: {
            color: '#f59e0b',
            bgColor: '#fffbeb',
            borderColor: '#fef3c7',
            icon: 'fas fa-exclamation-triangle'
        },
        medium: {
            color: '#f59e0b',
            bgColor: '#fffbeb',
            borderColor: '#fef3c7',
            icon: 'fas fa-exclamation-triangle'
        },
        high: {
            color: '#ef4444',
            bgColor: '#fef2f2',
            borderColor: '#fecaca',
            icon: 'fas fa-exclamation-circle'
        }
    },

    // Mock data for development/testing
    MOCK_DATA: {
        enabled: false, // Set to false when connecting to real API
        data: {
            currentFloodRisk: {
                status: 'Moderate',
                level: 'medium',
                confidence: 85,
                lastUpdate: new Date().toISOString()
            },
            riverLevel: {
                riverName: 'Thames River',
                stationName: 'Kingston Station',
                currentLevel: 2.5,
                unit: 'm',
                normalLevel: 2.0,
                dangerLevel: 4.0,
                lastUpdate: new Date().toISOString()
            },
            forecastRain: [
                { day: 'Mon', date: '2024-01-15', rainfall: 5.2, probability: 70 },
                { day: 'Tue', date: '2024-01-16', rainfall: 12.8, probability: 85 },
                { day: 'Wed', date: '2024-01-17', rainfall: 3.1, probability: 45 },
                { day: 'Thu', date: '2024-01-18', rainfall: 8.4, probability: 65 },
                { day: 'Fri', date: '2024-01-19', rainfall: 15.6, probability: 90 }
            ],
            forecastRiver: [
                { day: 'Mon', date: '2024-01-15', level: 2.3 },
                { day: 'Tue', date: '2024-01-16', level: 2.8 },
                { day: 'Wed', date: '2024-01-17', level: 2.1 },
                { day: 'Thu', date: '2024-01-18', level: 2.6 },
                { day: 'Fri', date: '2024-01-19', level: 3.2 }
            ],
            historyRiver: generateHistoryData(),
            rainfallComparison: [
                { month: 'Current Month', rainfall: 142.5, days: 15 },
                { month: 'Last Month', rainfall: 98.2, days: 31 }
            ],
            systemStatus: {
                activeSensors: 12,
                totalSensors: 12,
                lastUpdate: new Date(),
                status: 'online',
                uptime: '99.2%'
            }
        }
    },

    // UI Configuration
    UI: {
        // Animation durations
        animations: {
            cardHover: 200,
            loading: 300,
            modal: 300
        },
        
        // Auto-refresh settings
        autoRefresh: true,
        
        // Show debug information
        debug: false,
        
        // Logo configuration
        logo: {
            src: '\frontend\matsya_logo.png',
            alt: 'Dashboard Logo',
            width: '75px',
            height: '75px'
        }
    },

    // Error handling
    ERROR_HANDLING: {
        showErrorModal: true,
        autoRetry: true,
        maxRetryAttempts: 3,
        retryDelay: 2000,
        fallbackToMockData: false
    }
};

// Helper function to generate mock history data
function generateHistoryData() {
    const data = [];
    const today = new Date();
    
    for (let i = 29; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(date.getDate() - i);
        
        // Generate realistic river level data with some variation
        const baseLevel = 2.0;
        const seasonalVariation = Math.sin((i / 30) * Math.PI) * 0.3;
        const randomVariation = (Math.random() - 0.5) * 0.4;
        const trendVariation = (30 - i) * 0.01; // Slight upward trend
        
        const level = baseLevel + seasonalVariation + randomVariation + trendVariation;
        
        data.push({
            day: i + 1,
            date: date.toISOString().split('T')[0],
            level: Math.max(0.5, Math.round(level * 100) / 100), // Minimum 0.5m, round to 2 decimals
            timestamp: date.toISOString()
        });
    }
    
    return data;
}

// Utility function to get full API URL
function getApiUrl(endpoint) {
    return CONFIG.API.BASE_URL + CONFIG.API.ENDPOINTS[endpoint];
}

// Utility function to get risk level configuration
function getRiskConfig(level) {
    const normalizedLevel = level?.toLowerCase();
    return CONFIG.RISK_LEVELS[normalizedLevel] || CONFIG.RISK_LEVELS.low;
}

// Export configuration for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CONFIG;
}