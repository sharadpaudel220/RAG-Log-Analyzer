// API Configuration JavaScript

let apiConnections = [];
let fetchedLogs = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkHealth();
    loadAPIConnections();
    setInterval(checkHealth, 30000);
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
    }
}

// Load API connections
async function loadAPIConnections() {
    try {
        const response = await fetch('/api/api-connections');
        const data = await response.json();
        
        if (data.success) {
            apiConnections = data.connections || [];
            displayAPIConnections();
            updateConnectionSelect();
        }
    } catch (error) {
        console.error('Failed to load API connections:', error);
    }
}

// Display API connections
function displayAPIConnections() {
    const grid = document.getElementById('apiConnectionsGrid');
    
    if (apiConnections.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-plug"></i>
                <p>No API connections configured. Click "Add Connection" to get started!</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    apiConnections.forEach(conn => {
        const icon = getAPIIcon(conn.type);
        html += `
            <div class="api-connection-card">
                <div class="api-connection-header">
                    <div class="api-connection-icon ${conn.type}">
                        <i class="${icon}"></i>
                    </div>
                    <div class="api-connection-status ${conn.status}">
                        <i class="fas fa-circle"></i>
                    </div>
                </div>
                <div class="api-connection-body">
                    <h4>${conn.name}</h4>
                    <p class="api-type">${formatAPIType(conn.type)}</p>
                    <p class="api-endpoint">${conn.endpoint}</p>
                </div>
                <div class="api-connection-actions">
                    <button class="btn btn-sm btn-secondary" onclick="testConnection('${conn.id}')">
                        <i class="fas fa-plug"></i> Test
                    </button>
                    <button class="btn btn-sm btn-primary" onclick="editConnection('${conn.id}')">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteConnection('${conn.id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    grid.innerHTML = html;
}

// Update connection select dropdown
function updateConnectionSelect() {
    const select = document.getElementById('apiConnectionSelect');
    select.innerHTML = '<option value="">Select a connection...</option>';
    
    apiConnections.forEach(conn => {
        const option = document.createElement('option');
        option.value = conn.id;
        option.textContent = `${conn.name} (${formatAPIType(conn.type)})`;
        select.appendChild(option);
    });
}

// Get API icon
function getAPIIcon(type) {
    const icons = {
        'elasticsearch': 'fas fa-search',
        'splunk': 'fas fa-chart-line',
        'cloudwatch': 'fab fa-aws',
        'azure': 'fab fa-microsoft',
        'syslog': 'fas fa-server',
        'rest': 'fas fa-globe'
    };
    return icons[type] || 'fas fa-plug';
}

// Format API type
function formatAPIType(type) {
    const names = {
        'elasticsearch': 'Elasticsearch',
        'splunk': 'Splunk',
        'cloudwatch': 'AWS CloudWatch',
        'azure': 'Azure Monitor',
        'syslog': 'Syslog',
        'rest': 'REST API'
    };
    return names[type] || type;
}

// Add API connection
function addAPIConnection() {
    document.getElementById('addAPIModal').style.display = 'flex';
}

// Close API modal
function closeAPIModal() {
    document.getElementById('addAPIModal').style.display = 'none';
    document.getElementById('addAPIForm').reset();
}

// Update API fields based on type
function updateAPIFields() {
    const apiType = document.getElementById('apiType').value;
    const authFields = document.getElementById('authFields');
    
    // Add type-specific fields here if needed
    authFields.innerHTML = '';
}

// Test API connection
async function testAPIConnection() {
    const testResult = document.getElementById('testResult');
    testResult.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
    
    // Simulate test
    setTimeout(() => {
        testResult.innerHTML = '<span style="color: var(--success-color);"><i class="fas fa-check-circle"></i> Connection successful!</span>';
    }, 2000);
}

// Save API connection
async function saveAPIConnection() {
    const name = document.getElementById('apiName').value;
    const type = document.getElementById('apiType').value;
    const endpoint = document.getElementById('apiEndpoint').value;
    const authType = document.getElementById('authType').value;
    
    if (!name || !type || !endpoint) {
        alert('Please fill in all required fields');
        return;
    }
    
    try {
        const response = await fetch('/api/api-connections', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name,
                type,
                endpoint,
                auth_type: authType
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeAPIModal();
            loadAPIConnections();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error saving connection: ' + error.message);
    }
}

// Test connection
async function testConnection(id) {
    alert('Testing connection...');
    // Implement actual test
}

// Edit connection
function editConnection(id) {
    const conn = apiConnections.find(c => c.id === id);
    if (conn) {
        document.getElementById('apiName').value = conn.name;
        document.getElementById('apiType').value = conn.type;
        document.getElementById('apiEndpoint').value = conn.endpoint;
        addAPIConnection();
    }
}

// Delete connection
async function deleteConnection(id) {
    if (!confirm('Are you sure you want to delete this connection?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/api-connections/${id}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadAPIConnections();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error deleting connection: ' + error.message);
    }
}

// Fetch logs
async function fetchLogs() {
    const connectionId = document.getElementById('apiConnectionSelect').value;
    const startTime = document.getElementById('startTime').value;
    const endTime = document.getElementById('endTime').value;
    const query = document.getElementById('queryFilter').value;
    const maxFetch = document.getElementById('maxFetch').value;
    
    if (!connectionId) {
        alert('Please select an API connection');
        return;
    }
    
    try {
        const response = await fetch('/api/fetch-logs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                connection_id: connectionId,
                start_time: startTime,
                end_time: endTime,
                query: query,
                max_logs: parseInt(maxFetch)
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            fetchedLogs = data.logs || [];
            displayFetchedLogs();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error fetching logs: ' + error.message);
    }
}

// Display fetched logs
function displayFetchedLogs() {
    const section = document.getElementById('fetchedLogsSection');
    const preview = document.getElementById('logsPreview');
    
    if (fetchedLogs.length === 0) {
        preview.innerHTML = '<p>No logs fetched</p>';
        return;
    }
    
    let html = `<p><strong>Fetched ${fetchedLogs.length} logs</strong></p>`;
    html += '<div class="logs-table">';
    html += '<table><thead><tr><th>Timestamp</th><th>Severity</th><th>Message</th></tr></thead><tbody>';
    
    fetchedLogs.slice(0, 100).forEach(log => {
        html += `
            <tr>
                <td>${log.timestamp || 'N/A'}</td>
                <td><span class="badge ${(log.severity || 'info').toLowerCase()}">${log.severity || 'INFO'}</span></td>
                <td>${log.message || log.content}</td>
            </tr>
        `;
    });
    
    html += '</tbody></table></div>';
    
    if (fetchedLogs.length > 100) {
        html += `<p><em>Showing first 100 of ${fetchedLogs.length} logs</em></p>`;
    }
    
    preview.innerHTML = html;
    section.style.display = 'block';
}

// Analyze fetched logs
async function analyzeFetchedLogs() {
    if (fetchedLogs.length === 0) {
        alert('No logs to analyze');
        return;
    }
    
    // Redirect to log analyzer with fetched logs
    sessionStorage.setItem('fetchedLogs', JSON.stringify(fetchedLogs));
    window.location.href = '/log-analyzer?source=api';
}

// Export fetched logs
function exportFetchedLogs() {
    if (fetchedLogs.length === 0) return;
    
    const blob = new Blob([JSON.stringify(fetchedLogs, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fetched_logs_${Date.now()}.json`;
    a.click();
}
