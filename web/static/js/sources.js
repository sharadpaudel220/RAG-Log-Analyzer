// Log Sources Management JavaScript

// Global state
let captureInterval = null;

// Toggle log type sections
function toggleLogType(type) {
    const content = document.getElementById(`${type}-content`);
    const toggle = document.getElementById(`${type}-toggle`);
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggle.classList.add('open');
    } else {
        content.style.display = 'none';
        toggle.classList.remove('open');
    }
}

// Switch between API and Network Capture connection types
function switchNetworkConnectionType(type) {
    const apiBtn = document.getElementById('network-api-btn');
    const captureBtn = document.getElementById('network-capture-btn');
    const apiForm = document.getElementById('network-api-form');
    const captureForm = document.getElementById('network-capture-form');
    
    if (type === 'api') {
        apiBtn.classList.add('active');
        captureBtn.classList.remove('active');
        apiForm.style.display = 'block';
        captureForm.style.display = 'none';
    } else {
        apiBtn.classList.remove('active');
        captureBtn.classList.add('active');
        apiForm.style.display = 'none';
        captureForm.style.display = 'block';
    }
}

// Update capture filter based on preset selection
function updateCaptureFilter() {
    const preset = document.getElementById('capture-filter-preset').value;
    const customFilterDiv = document.getElementById('capture-custom-filter');
    
    if (preset === 'custom') {
        customFilterDiv.style.display = 'block';
    } else {
        customFilterDiv.style.display = 'none';
    }
}

// Update authentication fields based on auth type
function updateAuthFields(sourceType) {
    const authType = document.getElementById(`${sourceType}-auth-type`).value;
    const authFieldsDiv = document.getElementById(`${sourceType}-auth-fields`);
    
    let html = '';
    
    switch (authType) {
        case 'apikey':
            html = `
                <div class="form-group">
                    <label>API Key</label>
                    <input type="password" id="${sourceType}-api-key" placeholder="Enter API key" class="form-input">
                </div>
                <div class="form-group">
                    <label>API Key Header Name (optional)</label>
                    <input type="text" id="${sourceType}-api-key-header" placeholder="X-API-Key" class="form-input" value="X-API-Key">
                </div>
            `;
            break;
        case 'bearer':
            html = `
                <div class="form-group">
                    <label>Bearer Token</label>
                    <input type="password" id="${sourceType}-bearer-token" placeholder="Enter bearer token" class="form-input">
                </div>
            `;
            break;
        case 'basic':
            html = `
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" id="${sourceType}-username" placeholder="Enter username" class="form-input">
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" id="${sourceType}-password" placeholder="Enter password" class="form-input">
                </div>
            `;
            break;
        case 'oauth':
            html = `
                <div class="form-group">
                    <label>OAuth Token URL</label>
                    <input type="text" id="${sourceType}-oauth-url" placeholder="https://oauth.example.com/token" class="form-input">
                </div>
                <div class="form-group">
                    <label>Client ID</label>
                    <input type="text" id="${sourceType}-client-id" placeholder="Enter client ID" class="form-input">
                </div>
                <div class="form-group">
                    <label>Client Secret</label>
                    <input type="password" id="${sourceType}-client-secret" placeholder="Enter client secret" class="form-input">
                </div>
            `;
            break;
    }
    
    authFieldsDiv.innerHTML = html;
}

// Test network capture
async function testNetworkCapture() {
    const resultDiv = document.getElementById('network-capture-result');
    resultDiv.className = 'test-result';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing network capture...';
    resultDiv.style.display = 'block';
    
    try {
        const response = await fetch('/api/network-capture/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                interface: document.getElementById('capture-interface').value
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            resultDiv.className = 'test-result success';
            resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${result.message}`;
        } else {
            resultDiv.className = 'test-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${result.error || 'Test failed'}`;
        }
    } catch (error) {
        resultDiv.className = 'test-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> Error: ${error.message}`;
    }
}

// Start network capture
async function startNetworkCapture() {
    const resultDiv = document.getElementById('network-capture-result');
    const statsDiv = document.getElementById('network-capture-stats');
    const startBtn = document.querySelector('#network-capture-form .btn-primary');
    const stopBtn = document.getElementById('stop-capture-btn');
    
    resultDiv.className = 'test-result';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting network capture...';
    resultDiv.style.display = 'block';
    
    // Get filter
    const preset = document.getElementById('capture-filter-preset').value;
    let filter;
    
    switch (preset) {
        case 'all':
            filter = 'tcp or udp or icmp';
            break;
        case 'web':
            filter = 'port 80 or port 443';
            break;
        case 'dns':
            filter = 'port 53';
            break;
        case 'custom':
            filter = document.getElementById('capture-filter-custom').value || 'tcp or udp or icmp';
            break;
        default:
            filter = 'tcp or udp or icmp';
    }
    
    try {
        const response = await fetch('/api/network-capture/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: document.getElementById('capture-name').value,
                interface: document.getElementById('capture-interface').value,
                filter: filter,
                auto_analyze: document.getElementById('capture-auto-analyze').checked,
                store_logs: document.getElementById('capture-store-logs').checked
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            resultDiv.className = 'test-result success';
            resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${result.message}`;
            
            // Show stats and update UI
            statsDiv.style.display = 'block';
            startBtn.style.display = 'none';
            stopBtn.style.display = 'inline-flex';
            
            // Update network status badge
            document.getElementById('network-status').textContent = 'Connected';
            document.getElementById('network-status').classList.add('connected');
            
            // Start polling for stats
            startStatsPolling();
        } else {
            resultDiv.className = 'test-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${result.error || 'Failed to start capture'}`;
        }
    } catch (error) {
        resultDiv.className = 'test-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> Error: ${error.message}`;
    }
}

// Stop network capture
async function stopNetworkCapture() {
    const resultDiv = document.getElementById('network-capture-result');
    const statsDiv = document.getElementById('network-capture-stats');
    const startBtn = document.querySelector('#network-capture-form .btn-primary');
    const stopBtn = document.getElementById('stop-capture-btn');
    
    resultDiv.className = 'test-result';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping network capture...';
    resultDiv.style.display = 'block';
    
    try {
        const response = await fetch('/api/network-capture/stop', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            resultDiv.className = 'test-result success';
            resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> Capture stopped. ${result.stats?.logs_generated || 0} logs generated.`;
            
            // Update UI
            startBtn.style.display = 'inline-flex';
            stopBtn.style.display = 'none';
            
            // Update network status badge
            document.getElementById('network-status').textContent = 'Not Connected';
            document.getElementById('network-status').classList.remove('connected');
            
            // Stop polling
            stopStatsPolling();
        } else {
            resultDiv.className = 'test-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${result.error || 'Failed to stop capture'}`;
        }
    } catch (error) {
        resultDiv.className = 'test-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> Error: ${error.message}`;
    }
}

// Start polling for capture statistics
function startStatsPolling() {
    if (captureInterval) {
        clearInterval(captureInterval);
    }
    
    captureInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/network-capture/stats');
            const stats = await response.json();
            
            if (response.ok && stats) {
                document.getElementById('stat-packets').textContent = stats.packets_captured || 0;
                document.getElementById('stat-logs').textContent = stats.logs_generated || 0;
                document.getElementById('stat-rate').textContent = (stats.packets_per_second || 0).toFixed(1) + '/sec';
                document.getElementById('stat-uptime').textContent = formatUptime(stats.uptime_seconds || 0);
            }
        } catch (error) {
            console.error('Error fetching stats:', error);
        }
    }, 2000); // Update every 2 seconds
}

// Stop polling for statistics
function stopStatsPolling() {
    if (captureInterval) {
        clearInterval(captureInterval);
        captureInterval = null;
    }
}

// Format uptime in human-readable format
function formatUptime(seconds) {
    if (seconds < 60) {
        return Math.floor(seconds) + 's';
    } else if (seconds < 3600) {
        return Math.floor(seconds / 60) + 'm ' + Math.floor(seconds % 60) + 's';
    } else {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return hours + 'h ' + minutes + 'm';
    }
}

// Test API connection
async function testConnection(sourceType) {
    const resultDiv = document.getElementById(`${sourceType}-test-result`);
    resultDiv.className = 'test-result';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing connection...';
    resultDiv.style.display = 'block';
    
    // Simulate test (implement actual API call)
    setTimeout(() => {
        resultDiv.className = 'test-result success';
        resultDiv.innerHTML = '<i class="fas fa-check-circle"></i> Connection successful!';
    }, 1500);
}

// Save API connection
async function saveConnection(sourceType) {
    const resultDiv = document.getElementById(`${sourceType}-test-result`);
    resultDiv.className = 'test-result';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving connection...';
    resultDiv.style.display = 'block';
    
    // Simulate save (implement actual API call)
    setTimeout(() => {
        resultDiv.className = 'test-result success';
        resultDiv.innerHTML = '<i class="fas fa-check-circle"></i> Connection saved successfully!';
        
        // Update status badge
        document.getElementById(`${sourceType}-status`).textContent = 'Connected';
        document.getElementById(`${sourceType}-status`).classList.add('connected');
    }, 1500);
}

// Check system status on page load
async function checkSystemStatus() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        
        if (data.status === 'healthy') {
            statusDot.style.background = '#10b981';
            statusText.textContent = 'System Online';
        } else {
            statusDot.style.background = '#f59e0b';
            statusText.textContent = 'System Initializing';
        }
    } catch (error) {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        statusDot.style.background = '#ef4444';
        statusText.textContent = 'System Offline';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkSystemStatus();
    
    // Check if network capture is already running
    fetch('/api/network-capture/status')
        .then(response => response.json())
        .then(data => {
            if (data.running) {
                document.getElementById('network-status').textContent = 'Connected';
                document.getElementById('network-status').classList.add('connected');
                document.getElementById('network-capture-stats').style.display = 'block';
                document.querySelector('#network-capture-form .btn-primary').style.display = 'none';
                document.getElementById('stop-capture-btn').style.display = 'inline-flex';
                startStatsPolling();
            }
        })
        .catch(error => console.error('Error checking capture status:', error));
});
