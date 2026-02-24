// Dashboard JavaScript

let systemStats = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkHealth();
    loadStats();
    loadAlerts();
    loadSystemStatus();
    loadRecentSessions();
    setInterval(checkHealth, 30000); // Check health every 30 seconds
    setInterval(loadStats, 10000); // Update stats every 10 seconds
    setInterval(loadSystemStatus, 30000); // Update system status every 30 seconds
    setInterval(loadRecentSessions, 30000); // Update sessions every 30 seconds
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

// Load recent analysis sessions
async function loadRecentSessions() {
    try {
        const response = await fetch('/api/analysis-sessions');
        const data = await response.json();
        
        const historyContainer = document.getElementById('historyContainer');
        
        if (data.success && data.sessions && data.sessions.length > 0) {
            const recentSessions = data.sessions.slice(0, 5); // Show only 5 most recent
            let html = '<div class="sessions-list">';
            
            recentSessions.forEach(session => {
                const time = new Date(session.timestamp).toLocaleString();
                const statusClass = session.status === 'completed' ? 'success' : 'warning';
                
                html += `
                    <div class="session-item" onclick="navigateToHistory()">
                        <div class="session-icon">
                            <i class="fas fa-file-alt"></i>
                        </div>
                        <div class="session-info">
                            <div class="session-name">${session.filename}</div>
                            <div class="session-meta">
                                <span><i class="fas fa-clock"></i> ${time}</span>
                                <span><i class="fas fa-list"></i> ${session.total_logs} logs</span>
                                <span class="anomaly-badge ${session.anomalies_detected > 0 ? 'has-anomalies' : ''}">
                                    <i class="fas fa-exclamation-triangle"></i> ${session.anomalies_detected} anomalies
                                </span>
                            </div>
                        </div>
                        <div class="session-status">
                            <span class="status-badge ${statusClass}">${session.status}</span>
                            <button class="delete-btn-small" onclick="deleteSessionFromDashboard(event, '${session.session_id}')" title="Delete session">
                                <i class="fas fa-trash"></i>
                            </button>
                            <i class="fas fa-chevron-right"></i>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            historyContainer.innerHTML = html;
        } else {
            historyContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-clock"></i>
                    <p>No analysis sessions yet. Upload and analyze logs to get started!</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load recent sessions:', error);
        document.getElementById('historyContainer').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-circle"></i>
                <p>Error loading sessions</p>
            </div>
        `;
    }
}

// Navigate to analysis history
function navigateToHistory() {
    window.location.href = '/analysis-history';
}

// Toast notification system
function showToast(message, type = 'info', duration = 3000) {
    const toastContainer = document.getElementById('toastContainer') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    }[type] || 'fa-info-circle';
    
    toast.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

function showDeleteConfirmation(sessionId) {
    const toastContainer = document.getElementById('toastContainer') || createToastContainer();
    
    const confirmToast = document.createElement('div');
    confirmToast.className = 'toast toast-confirm';
    confirmToast.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-exclamation-triangle"></i>
            <span>Delete this analysis session?</span>
        </div>
        <div class="toast-actions">
            <button class="toast-btn toast-btn-cancel" onclick="this.closest('.toast').remove()">Cancel</button>
            <button class="toast-btn toast-btn-confirm" onclick="confirmDelete('${sessionId}', this)">Delete</button>
        </div>
    `;
    
    toastContainer.appendChild(confirmToast);
}

async function confirmDelete(sessionId, button) {
    const toast = button.closest('.toast');
    toast.remove();
    
    try {
        const response = await fetch(`/api/analysis-sessions/${sessionId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('Analysis session deleted successfully', 'success');
            loadRecentSessions();
            loadStats();
        } else {
            showToast('Error deleting session: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error deleting session:', error);
        showToast('Error deleting session', 'error');
    }
}

// Delete session from dashboard
async function deleteSessionFromDashboard(event, sessionId) {
    event.stopPropagation();
    showDeleteConfirmation(sessionId);
}

// Refresh data
function refreshData() {
    loadStats();
    loadAlerts();
    loadSystemStatus();
    loadRecentSessions();
}
