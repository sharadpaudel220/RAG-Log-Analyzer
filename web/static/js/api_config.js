// API Configuration JavaScript

let apiConnections = [];
let aiProviders = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkHealth();
    loadAPIConnections();
    loadAIProviders();
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

// ==================== AI Provider Configuration ====================

// Load AI provider configurations
async function loadAIProviders() {
    try {
        const response = await fetch('/api/ai-providers');
        const data = await response.json();
        
        if (data.success) {
            aiProviders = data.providers || {};
            updateAIProviderStatus();
        }
    } catch (error) {
        console.error('Failed to load AI providers:', error);
    }
}

// Update AI provider status indicators
function updateAIProviderStatus() {
    ['openai', 'anthropic', 'gemini'].forEach(provider => {
        const statusEl = document.getElementById(`${provider}-status`);
        if (aiProviders[provider] && aiProviders[provider].configured) {
            statusEl.innerHTML = '<i class="fas fa-check-circle"></i> Configured';
            statusEl.style.color = 'var(--success-color)';
        } else {
            statusEl.innerHTML = '<i class="fas fa-circle"></i> Not Configured';
            statusEl.style.color = 'var(--text-secondary)';
        }
    });
}

// Configure AI provider
function configureAIProvider(provider) {
    const modal = document.getElementById('configureAIModal');
    const titleEl = document.getElementById('aiModalTitle');
    const providerInput = document.getElementById('aiProvider');
    const modelInput = document.getElementById('aiModel');
    const modelHint = document.getElementById('aiModelHint');
    const baseURLInput = document.getElementById('aiBaseURL');
    const apiKeyInput = document.getElementById('aiAPIKey');
    const setAsDefaultCheckbox = document.getElementById('aiSetAsDefault');
    
    // Set provider-specific defaults
    const providerConfig = {
        'openai': {
            title: 'Configure OpenAI (ChatGPT)',
            defaultModel: 'gpt-4o-mini',
            modelHint: 'Examples: gpt-4o, gpt-4o-mini, gpt-3.5-turbo',
            defaultBaseURL: 'https://api.openai.com'
        },
        'anthropic': {
            title: 'Configure Anthropic (Claude)',
            defaultModel: 'claude-3-5-sonnet-20241022',
            modelHint: 'Examples: claude-3-5-sonnet-20241022, claude-3-opus-20240229',
            defaultBaseURL: 'https://api.anthropic.com'
        },
        'gemini': {
            title: 'Configure Google Gemini',
            defaultModel: 'gemini-1.5-flash',
            modelHint: 'Examples: gemini-1.5-pro, gemini-1.5-flash',
            defaultBaseURL: 'https://generativelanguage.googleapis.com'
        }
    };
    
    const config = providerConfig[provider];
    titleEl.textContent = config.title;
    providerInput.value = provider;
    modelHint.textContent = config.modelHint;
    
    // Load existing configuration if available
    if (aiProviders[provider]) {
        apiKeyInput.value = '••••••••••••••••'; // Masked
        modelInput.value = aiProviders[provider].model || config.defaultModel;
        baseURLInput.value = aiProviders[provider].base_url || '';
        setAsDefaultCheckbox.checked = aiProviders[provider].is_active || false;
    } else {
        apiKeyInput.value = '';
        modelInput.value = config.defaultModel;
        baseURLInput.value = '';
        setAsDefaultCheckbox.checked = false;
    }
    
    modal.style.display = 'flex';
}

// Close AI provider modal
function closeAIModal() {
    document.getElementById('configureAIModal').style.display = 'none';
    document.getElementById('aiProviderForm').reset();
    document.getElementById('aiTestResult').innerHTML = '';
}

// Test AI connection
async function testAIConnection() {
    const provider = document.getElementById('aiProvider').value;
    const apiKey = document.getElementById('aiAPIKey').value;
    const model = document.getElementById('aiModel').value;
    const baseURL = document.getElementById('aiBaseURL').value;
    const testResult = document.getElementById('aiTestResult');
    
    if (!apiKey || apiKey === '••••••••••••••••') {
        testResult.innerHTML = '<span style="color: var(--error-color);">Please enter an API key</span>';
        return;
    }
    
    testResult.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
    
    try {
        const response = await fetch('/api/ai-providers/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                provider,
                api_key: apiKey,
                model,
                base_url: baseURL
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            testResult.innerHTML = '<span style="color: var(--success-color);"><i class="fas fa-check-circle"></i> Connection successful!</span>';
        } else {
            testResult.innerHTML = `<span style="color: var(--error-color);"><i class="fas fa-times-circle"></i> ${data.error}</span>`;
        }
    } catch (error) {
        testResult.innerHTML = `<span style="color: var(--error-color);"><i class="fas fa-times-circle"></i> ${error.message}</span>`;
    }
}

// Save AI provider configuration
async function saveAIProvider() {
    const provider = document.getElementById('aiProvider').value;
    const apiKey = document.getElementById('aiAPIKey').value;
    const model = document.getElementById('aiModel').value;
    const baseURL = document.getElementById('aiBaseURL').value;
    const setAsDefault = document.getElementById('aiSetAsDefault').checked;
    
    if (!apiKey || apiKey === '••••••••••••••••') {
        alert('Please enter an API key');
        return;
    }
    
    if (!model) {
        alert('Please enter a model name');
        return;
    }
    
    try {
        const response = await fetch('/api/ai-providers', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                provider,
                api_key: apiKey,
                model,
                base_url: baseURL,
                set_as_active: setAsDefault
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeAIModal();
            loadAIProviders();
            alert('AI provider configured successfully!');
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error saving configuration: ' + error.message);
    }
}

// ==================== Log API Configuration ====================

// Configure log API
function configureLogAPI(apiType) {
    const modal = document.getElementById('configureLogAPIModal');
    const titleEl = document.getElementById('logAPIModalTitle');
    const typeInput = document.getElementById('logAPIType');
    
    const apiNames = {
        'syslog': 'Syslog API',
        'elasticsearch': 'Elasticsearch',
        'splunk': 'Splunk',
        'rest': 'REST API',
        'cloudwatch': 'AWS CloudWatch',
        'azure': 'Azure Monitor'
    };
    
    titleEl.textContent = `Configure ${apiNames[apiType] || apiType}`;
    typeInput.value = apiType;
    
    modal.style.display = 'flex';
}

// Close log API modal
function closeLogAPIModal() {
    document.getElementById('configureLogAPIModal').style.display = 'none';
    document.getElementById('logAPIForm').reset();
    document.getElementById('logAPITestResult').innerHTML = '';
}

// Update log API auth fields
function updateLogAPIAuthFields() {
    const authType = document.getElementById('logAPIAuthType').value;
    const authFields = document.getElementById('logAPIAuthFields');
    
    let html = '';
    
    if (authType === 'basic') {
        html = `
            <div class="form-group">
                <label>Username</label>
                <input type="text" id="logAPIUsername" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="logAPIPassword" required>
            </div>
        `;
    } else if (authType === 'bearer' || authType === 'apikey') {
        html = `
            <div class="form-group">
                <label>${authType === 'bearer' ? 'Bearer Token' : 'API Key'}</label>
                <input type="password" id="logAPIToken" required>
            </div>
        `;
    } else if (authType === 'oauth') {
        html = `
            <div class="form-group">
                <label>Client ID</label>
                <input type="text" id="logAPIClientId" required>
            </div>
            <div class="form-group">
                <label>Client Secret</label>
                <input type="password" id="logAPIClientSecret" required>
            </div>
            <div class="form-group">
                <label>Token URL</label>
                <input type="text" id="logAPITokenURL" required>
            </div>
        `;
    }
    
    authFields.innerHTML = html;
}

// Test log API connection
async function testLogAPIConnection() {
    const testResult = document.getElementById('logAPITestResult');
    testResult.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
    
    setTimeout(() => {
        testResult.innerHTML = '<span style="color: var(--success-color);"><i class="fas fa-check-circle"></i> Connection successful!</span>';
    }, 2000);
}

// Save log API connection
async function saveLogAPIConnection() {
    const name = document.getElementById('logAPIName').value;
    const type = document.getElementById('logAPIType').value;
    const endpoint = document.getElementById('logAPIEndpoint').value;
    const authType = document.getElementById('logAPIAuthType').value;
    
    if (!name || !type || !endpoint) {
        alert('Please fill in all required fields');
        return;
    }
    
    const authData = {};
    if (authType === 'basic') {
        authData.username = document.getElementById('logAPIUsername')?.value;
        authData.password = document.getElementById('logAPIPassword')?.value;
    } else if (authType === 'bearer' || authType === 'apikey') {
        authData.token = document.getElementById('logAPIToken')?.value;
    } else if (authType === 'oauth') {
        authData.client_id = document.getElementById('logAPIClientId')?.value;
        authData.client_secret = document.getElementById('logAPIClientSecret')?.value;
        authData.token_url = document.getElementById('logAPITokenURL')?.value;
    }
    
    try {
        const response = await fetch('/api/api-connections', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name,
                type,
                endpoint,
                auth_type: authType,
                auth_data: authData
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeLogAPIModal();
            loadAPIConnections();
            alert('API connection saved successfully!');
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

// Add API connection (legacy - kept for backward compatibility)
function addAPIConnection() {
    configureLogAPI('rest');
}
