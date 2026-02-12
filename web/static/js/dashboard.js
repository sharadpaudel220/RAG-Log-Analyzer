// Dashboard JavaScript

let systemStats = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkHealth();
    loadStats();
    loadAlerts();
    loadSystemStatus();
    setInterval(checkHealth, 30000); // Check health every 30 seconds
    setInterval(loadStats, 10000); // Update stats every 10 seconds
    setInterval(loadSystemStatus, 30000); // Update system status every 30 seconds
});

// Check system health
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        
        if (data.status === 'healthy') {
            statusDot.style.background = '#10b981';
            statusText.textContent = 'System Healthy';
        } else {
            statusDot.style.background = '#f59e0b';
            statusText.textContent = 'Initializing...';
        }
    } catch (error) {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        statusDot.style.background = '#ef4444';
        statusText.textContent = 'System Error';
        console.error('Health check failed:', error);
    }
}

// Load system statistics
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        systemStats = data;
        
        document.getElementById('totalLogs').textContent = data.total_logs_analyzed || 0;
        document.getElementById('anomaliesDetected').textContent = data.anomalies_detected || 0;
        document.getElementById('alertsGenerated').textContent = data.alerts_generated || 0;
        document.getElementById('knowledgeBase').textContent = data.knowledge_base_size || 0;
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// Load system status
async function loadSystemStatus() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        // LLM Status
        const llmStatus = document.getElementById('llmStatus');
        if (data.components && data.components.llm_engine) {
            llmStatus.innerHTML = '<span class="status-indicator active"></span> Online';
        } else {
            llmStatus.innerHTML = '<span class="status-indicator inactive"></span> Offline';
        }
        
        // Knowledge Base Status
        const kbStatus = document.getElementById('kbStatus');
        if (data.components && data.components.knowledge_base > 0) {
            kbStatus.innerHTML = `<span class="status-indicator active"></span> ${data.components.knowledge_base} documents`;
        } else {
            kbStatus.innerHTML = '<span class="status-indicator inactive"></span> Not loaded';
        }
        
        // Sources Status
        const sourcesStatus = document.getElementById('sourcesStatus');
        if (data.components && data.components.log_sources) {
            sourcesStatus.innerHTML = `<span class="status-indicator active"></span> ${data.components.log_sources} sources`;
        } else {
            sourcesStatus.innerHTML = '<span class="status-indicator inactive"></span> 0 sources';
        }
        
        // Uptime
        const uptimeStatus = document.getElementById('uptimeStatus');
        if (systemStats.uptime_start) {
            const uptime = new Date() - new Date(systemStats.uptime_start);
            const hours = Math.floor(uptime / (1000 * 60 * 60));
            const minutes = Math.floor((uptime % (1000 * 60 * 60)) / (1000 * 60));
            uptimeStatus.innerHTML = `<span class="status-indicator active"></span> ${hours}h ${minutes}m`;
        } else {
            uptimeStatus.innerHTML = '<span class="status-indicator active"></span> Running';
        }
    } catch (error) {
        console.error('Failed to load system status:', error);
    }
}

// Load recent alerts
async function loadAlerts() {
    try {
        const response = await fetch('/api/alerts');
        const data = await response.json();
        
        const alertsContainer = document.getElementById('alertsContainer');
        
        if (data.alerts && data.alerts.length > 0) {
            let html = '';
            data.alerts.forEach(alert => {
                const time = new Date(alert.timestamp).toLocaleString();
                html += `
                    <div class="alert-item">
                        <div class="alert-header">
                            <span class="alert-severity ${alert.severity}">${alert.severity}</span>
                            <span class="alert-time">${time}</span>
                        </div>
                        <div class="alert-description">${alert.description}</div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">
                            System: ${alert.system} | Analysis: ${(alert.analysis_time * 1000).toFixed(0)}ms
                        </div>
                    </div>
                `;
            });
            alertsContainer.innerHTML = html;
        } else {
            alertsContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>No alerts yet. Analyze some logs to get started!</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load alerts:', error);
    }
}

// Refresh data
function refreshData() {
    loadStats();
    loadAlerts();
    loadSystemStatus();
}
