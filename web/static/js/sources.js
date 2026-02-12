// Log Sources Management JavaScript

let currentFilter = 'all';
let allSources = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkHealth();
    loadSources();
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

// Load sources
async function loadSources() {
    try {
        const response = await fetch('/api/sources');
        const data = await response.json();
        
        allSources = data.sources || [];
        displaySources(allSources);
    } catch (error) {
        console.error('Failed to load sources:', error);
        document.getElementById('sourcesGrid').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to load sources</p>
            </div>
        `;
    }
}

// Display sources
function displaySources(sources) {
    const grid = document.getElementById('sourcesGrid');
    
    if (sources.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-plug"></i>
                <p>No log sources configured. Click "Add Source" to get started!</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    sources.forEach(source => {
        const icon = getSourceIcon(source.source_type);
        const statusClass = source.enabled ? 'enabled' : 'disabled';
        const statusText = source.enabled ? 'Active' : 'Disabled';
        
        html += `
            <div class="source-card ${statusClass}">
                <div class="source-header">
                    <div class="source-icon ${source.source_type}">
                        <i class="${icon}"></i>
                    </div>
                    <div class="source-status ${statusClass}">${statusText}</div>
                </div>
                <div class="source-body">
                    <h4>${source.name}</h4>
                    <p class="source-type">${formatSourceType(source.source_type)}</p>
                    <p class="source-method">
                        <i class="fas fa-plug"></i> ${formatIngestionMethod(source.ingestion_method)}
                    </p>
                    <div class="source-stats">
                        <div class="stat">
                            <span class="stat-label">Total Logs</span>
                            <span class="stat-value">${source.total_logs_received || 0}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Last Received</span>
                            <span class="stat-value">${source.last_received ? new Date(source.last_received).toLocaleString() : 'Never'}</span>
                        </div>
                    </div>
                </div>
                <div class="source-actions">
                    <button class="btn btn-sm btn-secondary" onclick="viewSource('${source.id}')">
                        <i class="fas fa-eye"></i> View
                    </button>
                    <button class="btn btn-sm ${source.enabled ? 'btn-warning' : 'btn-success'}" 
                            onclick="toggleSource('${source.id}', ${source.enabled})">
                        <i class="fas fa-power-off"></i> ${source.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteSource('${source.id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    grid.innerHTML = html;
}

// Get source icon
function getSourceIcon(sourceType) {
    const icons = {
        'system': 'fas fa-server',
        'network': 'fas fa-network-wired',
        'application': 'fas fa-code',
        'security': 'fas fa-shield-alt',
        'database': 'fas fa-database',
        'web_server': 'fas fa-globe',
        'container': 'fas fa-box',
        'cloud': 'fas fa-cloud',
        'custom': 'fas fa-cog'
    };
    return icons[sourceType] || 'fas fa-file-alt';
}

// Format source type
function formatSourceType(type) {
    return type.split('_').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
}

// Format ingestion method
function formatIngestionMethod(method) {
    return method.split('_').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
}

// Filter sources
function filterSources(type) {
    currentFilter = type;
    
    // Update active filter chip
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Filter and display
    if (type === 'all') {
        displaySources(allSources);
    } else {
        const filtered = allSources.filter(s => s.source_type === type);
        displaySources(filtered);
    }
}

// Show add source modal
function showAddSourceModal() {
    document.getElementById('addSourceModal').style.display = 'flex';
}

// Close add source modal
function closeAddSourceModal() {
    document.getElementById('addSourceModal').style.display = 'none';
    document.getElementById('addSourceForm').reset();
}

// Create source
async function createSource() {
    const name = document.getElementById('sourceName').value;
    const id = document.getElementById('sourceId').value;
    const sourceType = document.getElementById('sourceType').value;
    const ingestionMethod = document.getElementById('ingestionMethod').value;
    const description = document.getElementById('sourceDescription').value;
    
    if (!name || !id || !sourceType || !ingestionMethod) {
        alert('Please fill in all required fields');
        return;
    }
    
    try {
        const response = await fetch('/api/sources', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: id,
                name: name,
                source_type: sourceType,
                ingestion_method: ingestionMethod,
                metadata: { description: description }
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeAddSourceModal();
            loadSources();
            
            // Show API key if generated
            if (data.api_key) {
                alert(`Source created successfully!\n\nAPI Key: ${data.api_key}\n\nPlease save this key securely. You won't be able to see it again.`);
            }
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error creating source: ' + error.message);
    }
}

// View source details
async function viewSource(sourceId) {
    try {
        const response = await fetch(`/api/sources/${sourceId}`);
        const source = await response.json();
        
        let html = `
            <div class="source-detail">
                <div class="detail-row">
                    <strong>Source ID:</strong>
                    <span>${source.id}</span>
                </div>
                <div class="detail-row">
                    <strong>Name:</strong>
                    <span>${source.name}</span>
                </div>
                <div class="detail-row">
                    <strong>Type:</strong>
                    <span>${formatSourceType(source.source_type)}</span>
                </div>
                <div class="detail-row">
                    <strong>Ingestion Method:</strong>
                    <span>${formatIngestionMethod(source.ingestion_method)}</span>
                </div>
                <div class="detail-row">
                    <strong>Status:</strong>
                    <span class="badge ${source.enabled ? 'normal' : 'anomaly'}">${source.enabled ? 'Active' : 'Disabled'}</span>
                </div>
                <div class="detail-row">
                    <strong>Total Logs Received:</strong>
                    <span>${source.total_logs_received || 0}</span>
                </div>
                <div class="detail-row">
                    <strong>Last Received:</strong>
                    <span>${source.last_received ? new Date(source.last_received).toLocaleString() : 'Never'}</span>
                </div>
                <div class="detail-row">
                    <strong>Created:</strong>
                    <span>${new Date(source.created_at).toLocaleString()}</span>
                </div>
        `;
        
        if (source.ingestion_method === 'api') {
            html += `
                <div class="detail-row">
                    <strong>API Endpoint:</strong>
                    <code>POST http://localhost:5001/api/ingest</code>
                </div>
                <div class="detail-row">
                    <strong>Header:</strong>
                    <code>X-API-Key: [your-api-key]</code>
                </div>
            `;
        } else if (source.ingestion_method === 'webhook') {
            html += `
                <div class="detail-row">
                    <strong>Webhook URL:</strong>
                    <code>POST http://localhost:5001/api/ingest/webhook/${source.id}</code>
                </div>
            `;
        }
        
        if (source.metadata && source.metadata.description) {
            html += `
                <div class="detail-row">
                    <strong>Description:</strong>
                    <span>${source.metadata.description}</span>
                </div>
            `;
        }
        
        html += `</div>`;
        
        document.getElementById('detailSourceName').textContent = source.name;
        document.getElementById('sourceDetailContent').innerHTML = html;
        document.getElementById('sourceDetailModal').style.display = 'flex';
    } catch (error) {
        alert('Error loading source details: ' + error.message);
    }
}

// Close source detail modal
function closeSourceDetailModal() {
    document.getElementById('sourceDetailModal').style.display = 'none';
}

// Toggle source
async function toggleSource(sourceId, currentlyEnabled) {
    const action = currentlyEnabled ? 'disable' : 'enable';
    
    try {
        const response = await fetch(`/api/sources/${sourceId}/${action}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadSources();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error toggling source: ' + error.message);
    }
}

// Delete source
async function deleteSource(sourceId) {
    if (!confirm('Are you sure you want to delete this source? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/sources/${sourceId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadSources();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error deleting source: ' + error.message);
    }
}

// Refresh sources
function refreshSources() {
    loadSources();
}
