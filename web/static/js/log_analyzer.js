// Log Analyzer JavaScript

let uploadedFile = null;
let analysisResults = null;
let currentSessionId = null;
let chatHistory = [];
let ollamaAvailable = false;

function showToast(message, type = 'info', title = null, timeoutMs = 7000) {
    const container = document.getElementById('toastContainer');
    if (!container) {
        return;
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const iconByType = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    const titleByType = {
        success: 'Success',
        error: 'Error',
        warning: 'Warning',
        info: 'Info'
    };

    const safeTitle = title || titleByType[type] || 'Info';
    const icon = iconByType[type] || iconByType.info;

    const header = document.createElement('div');
    header.className = 'toast-header';
    header.innerHTML = `
        <div class="toast-title">
            <i class="fas ${icon}"></i>
            <span>${safeTitle}</span>
        </div>
        <button class="toast-close" aria-label="Close">
            <i class="fas fa-times"></i>
        </button>
    `;

    const body = document.createElement('div');
    body.className = 'toast-body';
    body.textContent = message;

    toast.appendChild(header);
    toast.appendChild(body);
    container.appendChild(toast);

    const closeBtn = header.querySelector('.toast-close');
    const close = () => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    };
    closeBtn.addEventListener('click', close);

    if (timeoutMs && timeoutMs > 0) {
        setTimeout(close, timeoutMs);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkHealth();
    setupFileUpload();
    // loadConfiguredAPISources(); // Removed - old API sources UI replaced with new 3-option grid
    setInterval(checkHealth, 30000);
    updateOllamaStatus();
    setInterval(updateOllamaStatus, 10000);
    
    // Check if we're continuing an existing session
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    const filename = urlParams.get('filename');
    
    if (sessionId) {
        loadExistingSession(sessionId, filename);
    }
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
        console.error('Health check failed:', error);
    }
}

// Check Ollama status and update UI
async function updateOllamaStatus() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        ollamaAvailable = data.ollama_available || false;
        
        const ollamaStatus = document.getElementById('ollamaStatus');
        if (ollamaStatus) {
            if (ollamaAvailable) {
                ollamaStatus.innerHTML = '<i class="fas fa-circle" style="color: #10b981; font-size: 0.75rem;"></i> Ollama Active (Click for details)';
                ollamaStatus.style.color = '#10b981';
            } else {
                ollamaStatus.innerHTML = '<i class="fas fa-circle" style="color: #ef4444; font-size: 0.75rem;"></i> Ollama Inactive (Click for details)';
                ollamaStatus.style.color = '#ef4444';
            }
        }
        
        // Disable/enable Agentic RAG option based on Ollama status
        const agenticOption = document.getElementById('batchSystemSelect')?.querySelector('option[value="agentic"]');
        if (agenticOption) {
            if (!ollamaAvailable) {
                agenticOption.disabled = true;
                agenticOption.textContent = 'Agentic RAG (Ollama Required - Not Running)';
            } else {
                agenticOption.disabled = false;
                agenticOption.textContent = 'Agentic RAG';
            }
        }

        // Remove repeated toast warnings - only show once when status changes
        if (typeof window.lastOllamaStatus !== 'undefined' && window.lastOllamaStatus !== ollamaAvailable) {
            if (!ollamaAvailable) {
                showToast('Ollama is not running. Agentic RAG requires Ollama for ReAct-based analysis.', 'warning');
            }
        }
        window.lastOllamaStatus = ollamaAvailable;
    } catch (error) {
        console.error('Ollama status check failed:', error);
        ollamaAvailable = false;
    }
}

// Show Ollama details dialog
async function showOllamaDetails() {
    // Fetch Ollama model info
    let modelInfo = null;
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        if (data.ollama_available) {
            modelInfo = data.ollama_model || 'Unknown';
        }
    } catch (error) {
        console.error('Failed to fetch Ollama model info:', error);
    }

    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 500px;">
            <div class="modal-header">
                <h3><i class="fas fa-brain"></i> Ollama Status</h3>
                <button class="modal-close" onclick="this.closest('.modal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div style="margin-bottom: 1rem;">
                    <strong>Status:</strong>
                    <span style="margin-left: 0.5rem; color: ${ollamaAvailable ? '#10b981' : '#f59e0b'};">
                        ${ollamaAvailable ? 'Running' : 'Not Running'}
                    </span>
                </div>
                <div style="margin-bottom: 1rem;">
                    <strong>Base URL:</strong>
                    <span style="margin-left: 0.5rem; color: var(--text-secondary);">http://localhost:11434</span>
                </div>
                ${ollamaAvailable && modelInfo ? `
                <div style="margin-bottom: 1rem;">
                    <strong>LLM Model:</strong>
                    <span style="margin-left: 0.5rem; color: var(--text-secondary);">${modelInfo}</span>
                </div>
                ` : ''}
                <div style="margin-bottom: 1rem;">
                    <strong>Purpose:</strong>
                    <p style="color: var(--text-secondary); margin-top: 0.5rem;">
                        Ollama is required for Agentic RAG analysis to use the ReAct technique with local LLM models.
                    </p>
                </div>
                ${!ollamaAvailable ? `
                <div style="margin-bottom: 1rem; padding: 1rem; background: rgba(245, 158, 11, 0.1); border-radius: 8px; border: 1px solid rgba(245, 158, 11, 0.3);">
                    <strong style="color: #f59e0b;">How to start Ollama:</strong>
                    <ul style="color: var(--text-secondary); margin-top: 0.5rem; margin-left: 1.5rem;">
                        <li>Install Ollama from <a href="https://ollama.ai" target="_blank" style="color: var(--color-teal);">ollama.ai</a></li>
                        <li>Run: <code style="background: var(--glass-light); padding: 0.25rem 0.5rem; border-radius: 4px;">ollama serve</code></li>
                        <li>Ensure it's running on port 11434</li>
                    </ul>
                </div>
                ` : ''}
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" onclick="this.closest('.modal').remove()">Close</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Close on click outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Setup file upload
function setupFileUpload() {
    const fileInput = document.getElementById('fileInput');

    if (!fileInput) {
        console.error('File input element not found');
        return;
    }
    
    // File input is handled via onchange attribute in HTML
}

// Open network capture modal
async function openNetworkCaptureModal() {
    document.getElementById('networkCaptureModal').style.display = 'flex';

    // Check current capture status
    try {
        const response = await fetch('/api/network-capture/status');
        const data = await response.json();

        if (data.running) {
            // Show stop button if capture is running
            document.getElementById('networkCaptureStatus').style.display = 'block';
            document.getElementById('startNetworkCaptureBtn').style.display = 'none';
            document.getElementById('stopNetworkCaptureBtn').style.display = 'inline-block';
            document.getElementById('analyzeNetworkLogsBtn').style.display = 'none';
        } else {
            // Check if there are captured logs available
            try {
                const logsResponse = await fetch('/api/network-capture/logs');

                if (logsResponse.status === 400) {
                    // Log file is empty, show start button only
                    document.getElementById('networkCaptureStatus').style.display = 'none';
                    document.getElementById('startNetworkCaptureBtn').style.display = 'inline-block';
                    document.getElementById('stopNetworkCaptureBtn').style.display = 'none';
                    document.getElementById('analyzeNetworkLogsBtn').style.display = 'none';
                } else {
                    const logsData = await logsResponse.json();

                    if (logsResponse.ok && logsData.logs && logsData.logs.length > 0) {
                        // Show analyze button if logs are available
                        document.getElementById('networkCaptureStatus').style.display = 'none';
                        document.getElementById('startNetworkCaptureBtn').style.display = 'inline-block';
                        document.getElementById('stopNetworkCaptureBtn').style.display = 'none';
                        document.getElementById('analyzeNetworkLogsBtn').style.display = 'inline-block';
                    } else {
                        // Show start button if no logs available
                        document.getElementById('networkCaptureStatus').style.display = 'none';
                        document.getElementById('startNetworkCaptureBtn').style.display = 'inline-block';
                        document.getElementById('stopNetworkCaptureBtn').style.display = 'none';
                        document.getElementById('analyzeNetworkLogsBtn').style.display = 'none';
                    }
                }
            } catch (error) {
                console.error('Error checking network logs:', error);
                // Default to showing start button
                document.getElementById('networkCaptureStatus').style.display = 'none';
                document.getElementById('startNetworkCaptureBtn').style.display = 'inline-block';
                document.getElementById('stopNetworkCaptureBtn').style.display = 'none';
                document.getElementById('analyzeNetworkLogsBtn').style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error checking network capture status:', error);
        // Default to showing start button
        document.getElementById('networkCaptureStatus').style.display = 'none';
        document.getElementById('startNetworkCaptureBtn').style.display = 'inline-block';
        document.getElementById('stopNetworkCaptureBtn').style.display = 'none';
        document.getElementById('analyzeNetworkLogsBtn').style.display = 'none';
    }
}

function closeNetworkCaptureModal() {
    const modal = document.getElementById('networkCaptureModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function startNetworkCapture() {
    const interface = document.getElementById('networkInterface').value;
    const filter = document.getElementById('networkFilter').value;
    const maxPackets = parseInt(document.getElementById('maxPackets').value, 10) || 1000;

    try {
        const response = await fetch('/api/network-capture/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                interface: interface,
                filter: filter,
                max_packets: maxPackets,
                auto_analyze: false,
                store_logs: true
            })
        });

        const data = await response.json();

        if (response.ok) {
            showToast(`Network capture started on ${interface}`, 'success');
            // Update UI to show running state
            document.getElementById('networkCaptureStatus').style.display = 'block';
            document.getElementById('startNetworkCaptureBtn').style.display = 'none';
            document.getElementById('stopNetworkCaptureBtn').style.display = 'inline-block';
            document.getElementById('analyzeNetworkLogsBtn').style.display = 'none';
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error starting network capture:', error);
        showToast('Error starting network capture', 'error');
    }
}

async function stopNetworkCapture() {
    try {
        const response = await fetch('/api/network-capture/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Network capture stopped', 'success');
            // Update UI to show stopped state with analyze option
            document.getElementById('networkCaptureStatus').style.display = 'none';
            document.getElementById('startNetworkCaptureBtn').style.display = 'inline-block';
            document.getElementById('stopNetworkCaptureBtn').style.display = 'none';
            document.getElementById('analyzeNetworkLogsBtn').style.display = 'inline-block';
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error stopping network capture:', error);
        showToast('Error stopping network capture', 'error');
    }
}

async function analyzeCapturedNetworkLogs() {
    try {
        const response = await fetch('/api/network-capture/logs');

        if (response.status === 400) {
            showToast('No logs captured yet. The log file is empty. Please start capture and wait for logs to be collected.', 'warning');
            return;
        }

        const data = await response.json();

        if (response.ok && data.logs && data.logs.length > 0) {
            showToast(`Loaded ${data.logs.length} captured network logs`, 'success');
            closeNetworkCaptureModal();

            // Convert logs to file-like object
            const logContent = data.logs.map(log => log.content || JSON.stringify(log)).join('\n');
            const blob = new Blob([logContent], { type: 'text/plain' });
            const file = new File([blob], 'network_captured_logs.txt', { type: 'text/plain' });

            // Set the uploaded file
            uploadedFile = file;

            // Show file upload section with configuration
            document.getElementById('fileUploadSection').style.display = 'block';
            document.getElementById('fileName').textContent = file.name;
            document.getElementById('fileSize').textContent = (file.size / 1024).toFixed(2) + ' KB';

            // Set the analysis system from the modal
            document.getElementById('batchSystemSelect').value = document.getElementById('networkAnalysisSystem').value;

            // Scroll to file upload section
            document.getElementById('fileUploadSection').scrollIntoView({ behavior: 'smooth' });
        } else {
            showToast('No logs captured yet. Please start capture first.', 'warning');
        }
    } catch (error) {
        console.error('Error fetching network logs:', error);
        showToast('Error fetching network logs', 'error');
    }
}

async function fetchAndAnalyzeNetworkLogs(systemType) {
    try {
        const response = await fetch('/api/network-capture/logs');
        const data = await response.json();

        if (response.ok && data.logs && data.logs.length > 0) {
            // Analyze the logs
            await analyzeLogs(data.logs, systemType);
        }
    } catch (error) {
        console.error('Error fetching network logs:', error);
    }
}

async function fetchAndAnalyzeNetworkLogs(systemType) {
    showToast('Fetching captured logs...', 'info');

    try {
        const response = await fetch('/api/network-capture/logs');
        const data = await response.json();

        if (data.logs && data.logs.length > 0) {
            showToast(`Analyzing ${data.logs.length} captured logs...`, 'info');
            
            // Convert logs to file-like object for analysis
            const logContent = data.logs.map(log => log.content || JSON.stringify(log)).join('\n');
            const blob = new Blob([logContent], { type: 'text/plain' });
            const file = new File([blob], 'network_captured_logs.txt', { type: 'text/plain' });
            
            // Set the file and system type
            uploadedFile = file;
            
            // Show file upload section with configuration
            document.getElementById('fileUploadSection').style.display = 'block';
            document.getElementById('fileName').textContent = file.name;
            document.getElementById('fileSize').textContent = formatFileSize(file.size);
            document.getElementById('batchSystemSelect').value = systemType;
            
            // Scroll to configuration section
            document.getElementById('fileUploadSection').scrollIntoView({ behavior: 'smooth' });
        } else {
            showToast('No logs captured yet. Please wait a bit longer or check the network capture status.', 'warning');
        }
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

// System Log Modal Functions
async function openSystemLogModal() {
    const modal = document.getElementById('systemLogModal');
    if (modal) {
        modal.style.display = 'flex';
    }

    // Check current capture status
    try {
        const response = await fetch('/api/system-log/status');
        const data = await response.json();

        if (data.running) {
            // Show stop button if capture is running
            document.getElementById('systemLogCaptureStatus').style.display = 'block';
            document.getElementById('startSystemLogCaptureBtn').style.display = 'none';
            document.getElementById('stopSystemLogCaptureBtn').style.display = 'inline-block';
            document.getElementById('analyzeSystemLogsBtn').style.display = 'none';
        } else {
            // Check if there are captured logs available
            try {
                const logsResponse = await fetch('/api/system-log/logs');

                if (logsResponse.status === 400) {
                    // Log file is empty, show start button only
                    document.getElementById('systemLogCaptureStatus').style.display = 'none';
                    document.getElementById('startSystemLogCaptureBtn').style.display = 'inline-block';
                    document.getElementById('stopSystemLogCaptureBtn').style.display = 'none';
                    document.getElementById('analyzeSystemLogsBtn').style.display = 'none';
                } else {
                    const logsData = await logsResponse.json();

                    if (logsResponse.ok && logsData.logs && logsData.logs.length > 0) {
                        // Show analyze button if logs are available
                        document.getElementById('systemLogCaptureStatus').style.display = 'none';
                        document.getElementById('startSystemLogCaptureBtn').style.display = 'inline-block';
                        document.getElementById('stopSystemLogCaptureBtn').style.display = 'none';
                        document.getElementById('analyzeSystemLogsBtn').style.display = 'inline-block';
                    } else {
                        // Show start button if no logs available
                        document.getElementById('systemLogCaptureStatus').style.display = 'none';
                        document.getElementById('startSystemLogCaptureBtn').style.display = 'inline-block';
                        document.getElementById('stopSystemLogCaptureBtn').style.display = 'none';
                        document.getElementById('analyzeSystemLogsBtn').style.display = 'none';
                    }
                }
            } catch (error) {
                console.error('Error checking system logs:', error);
                // Default to showing start button
                document.getElementById('systemLogCaptureStatus').style.display = 'none';
                document.getElementById('startSystemLogCaptureBtn').style.display = 'inline-block';
                document.getElementById('stopSystemLogCaptureBtn').style.display = 'none';
                document.getElementById('analyzeSystemLogsBtn').style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error checking system log capture status:', error);
        // Default to showing start button
        document.getElementById('systemLogCaptureStatus').style.display = 'none';
        document.getElementById('startSystemLogCaptureBtn').style.display = 'inline-block';
        document.getElementById('stopSystemLogCaptureBtn').style.display = 'none';
        document.getElementById('analyzeSystemLogsBtn').style.display = 'none';
    }
}

function closeSystemLogModal() {
    const modal = document.getElementById('systemLogModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function startSystemLogCapture() {
    const logDirectory = document.getElementById('logDirectory').value;
    const logFilePattern = document.getElementById('logFilePattern').value;
    const refreshInterval = parseInt(document.getElementById('refreshInterval').value, 10) || 1;
    const maxLines = parseInt(document.getElementById('maxLines').value, 10) || 100;

    try {
        const response = await fetch('/api/system-log/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                log_directory: logDirectory,
                file_pattern: logFilePattern,
                refresh_interval: refreshInterval,
                max_lines: maxLines
            })
        });

        const data = await response.json();

        if (response.ok) {
            showToast(`System log capture started for ${logDirectory}`, 'success');
            // Update UI to show running state
            document.getElementById('systemLogCaptureStatus').style.display = 'block';
            document.getElementById('startSystemLogCaptureBtn').style.display = 'none';
            document.getElementById('stopSystemLogCaptureBtn').style.display = 'inline-block';
            document.getElementById('analyzeSystemLogsBtn').style.display = 'none';
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error starting system log capture:', error);
        showToast('Error starting system log capture', 'error');
    }
}

async function stopSystemLogCapture() {
    try {
        const response = await fetch('/api/system-log/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (response.ok) {
            showToast('System log capture stopped', 'success');
            // Update UI to show stopped state with analyze option
            document.getElementById('systemLogCaptureStatus').style.display = 'none';
            document.getElementById('startSystemLogCaptureBtn').style.display = 'inline-block';
            document.getElementById('stopSystemLogCaptureBtn').style.display = 'none';
            document.getElementById('analyzeSystemLogsBtn').style.display = 'inline-block';
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error stopping system log capture:', error);
        showToast('Error stopping system log capture', 'error');
    }
}

async function analyzeCapturedSystemLogs() {
    try {
        const response = await fetch('/api/system-log/logs');

        if (response.status === 400) {
            showToast('No logs captured yet. The log file is empty. Please start capture and wait for logs to be collected.', 'warning');
            return;
        }

        const data = await response.json();

        if (response.ok && data.logs && data.logs.length > 0) {
            showToast(`Loaded ${data.logs.length} captured system logs`, 'success');
            closeSystemLogModal();

            // Convert logs to file-like object
            const logContent = data.logs.map(log => log.content || JSON.stringify(log)).join('\n');
            const blob = new Blob([logContent], { type: 'text/plain' });
            const file = new File([blob], 'system_captured_logs.txt', { type: 'text/plain' });

            // Set the uploaded file
            uploadedFile = file;

            // Show file upload section with configuration
            document.getElementById('fileUploadSection').style.display = 'block';
            document.getElementById('fileName').textContent = file.name;
            document.getElementById('fileSize').textContent = (file.size / 1024).toFixed(2) + ' KB';

            // Set the analysis system from the modal
            document.getElementById('batchSystemSelect').value = document.getElementById('systemAnalysisSystem').value;

            // Scroll to file upload section
            document.getElementById('fileUploadSection').scrollIntoView({ behavior: 'smooth' });
        } else {
            showToast('No logs captured yet. Please start capture first.', 'warning');
        }
    } catch (error) {
        console.error('Error fetching system logs:', error);
        showToast('Error fetching system logs', 'error');
    }
}

async function fetchAndAnalyzeSystemLogs(systemType) {
    try {
        const response = await fetch('/api/system-log/logs');
        const data = await response.json();

        if (response.ok && data.logs && data.logs.length > 0) {
            // Analyze the logs
            await analyzeLogs(data.logs, systemType);
        }
    } catch (error) {
        console.error('Error fetching system logs:', error);
    }
}

async function fetchAndAnalyzeSystemLogs(systemType) {
    showToast('Fetching system logs...', 'info');

    try {
        const response = await fetch('/api/system-log/logs');
        const data = await response.json();

        if (data.logs && data.logs.length > 0) {
            showToast(`Analyzing ${data.logs.length} system logs...`, 'info');
            
            // Convert logs to file-like object for analysis
            const logContent = data.logs.map(log => log.content || JSON.stringify(log)).join('\n');
            const blob = new Blob([logContent], { type: 'text/plain' });
            const file = new File([blob], 'system_logs.txt', { type: 'text/plain' });
            
            // Set the file and system type
            uploadedFile = file;
            
            // Show file upload section with configuration
            document.getElementById('fileUploadSection').style.display = 'block';
            document.getElementById('fileName').textContent = file.name;
            document.getElementById('fileSize').textContent = formatFileSize(file.size);
            document.getElementById('batchSystemSelect').value = systemType;
            
            // Scroll to configuration section
            document.getElementById('fileUploadSection').scrollIntoView({ behavior: 'smooth' });
        } else {
            showToast('No logs found. Please check the log directory and file pattern.', 'warning');
        }
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

// Handle file selection from the new UI
function handleFile(file) {
    if (!file) return;

    const allowedTypes = ['.log', '.txt', '.json', '.csv'];
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowedTypes.includes(fileExt)) {
        showToast('Invalid file type. Please upload .log, .txt, .json, or .csv files.', 'warning');
        return;
    }

    uploadedFile = file;
    document.getElementById('fileUploadSection').style.display = 'block';
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
    
    // Scroll to configuration section
    document.getElementById('fileUploadSection').scrollIntoView({ behavior: 'smooth' });
}


// Remove file
function removeFile() {
    uploadedFile = null;
    document.getElementById('fileUploadSection').style.display = 'none';
    document.getElementById('fileInput').value = '';
}

// Format file size
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

// Analyze uploaded file
async function analyzeFile() {
    if (!uploadedFile) {
        showToast('Please upload a log file first.', 'warning');
        return;
    }

    const systemType = document.getElementById('batchSystemSelect').value;
    const maxLogs = parseInt(document.getElementById('maxLogs').value);
    const generateReport = document.getElementById('generateReport').checked;
    const exportJson = document.getElementById('exportJson').checked;

    showProgress('Uploading file...');

    try {
        const formData = new FormData();
        formData.append('file', uploadedFile);
        formData.append('system_type', systemType);
        formData.append('max_logs', maxLogs);
        formData.append('generate_report', generateReport);
        formData.append('export_json', exportJson);
        
        updateProgress(5, 'File uploaded, starting analysis...');
        
        const startTime = Date.now();
        let progressInterval;
        
        const uploadPromise = fetch('/api/analyze-file', {
            method: 'POST',
            body: formData
        });
        
        progressInterval = setInterval(() => {
            const elapsed = (Date.now() - startTime) / 1000;
            const estimatedProgress = Math.min(90, 10 + (elapsed / 2));
            updateProgress(estimatedProgress, `Analyzing logs... (${elapsed.toFixed(0)}s elapsed)`);
        }, 500);
        
        const uploadResponse = await uploadPromise;
        clearInterval(progressInterval);
        
        const uploadData = await uploadResponse.json();
        
        if (uploadData.success) {
            currentSessionId = uploadData.session_id;
            updateProgress(100, `Analysis complete! Found ${uploadData.anomalies_detected} anomalies in ${uploadData.total_time.toFixed(1)}s`);
            setTimeout(() => {
                displayBatchResults(uploadData);
                hideProgress();
            }, 1500);
        } else {
            hideProgress();
            showToast(uploadData.error || 'Unknown error analyzing file.', 'error');
        }
    } catch (error) {
        hideProgress();
        showToast(error.message || 'Unexpected error analyzing file.', 'error');
    }
}

// Display single result
function displaySingleResult(data) {
    const resultsSection = document.getElementById('resultsSection');
    const reportSummary = document.getElementById('reportSummary');
    const reportDetails = document.getElementById('reportDetails');
    
    analysisResults = data;
    
    // Summary
    reportSummary.innerHTML = `
        <div class="summary-cards">
            <div class="summary-card ${data.is_anomaly ? 'anomaly' : 'normal'}">
                <div class="summary-icon">
                    <i class="fas fa-${data.is_anomaly ? 'exclamation-triangle' : 'check-circle'}"></i>
                </div>
                <div class="summary-content">
                    <h4>${data.is_anomaly ? 'Anomaly Detected' : 'Normal Log'}</h4>
                    <p>Confidence: ${(data.confidence * 100).toFixed(2)}%</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon">
                    <i class="fas fa-clock"></i>
                </div>
                <div class="summary-content">
                    <h4>Analysis Time</h4>
                    <p>${data.analysis_time.toFixed(3)}s</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon">
                    <i class="fas fa-layer-group"></i>
                </div>
                <div class="summary-content">
                    <h4>System Used</h4>
                    <p>${document.getElementById('systemSelect').selectedOptions[0].text}</p>
                </div>
            </div>
        </div>
    `;
    
    // Details
    let detailsHTML = '<div class="report-section">';
    detailsHTML += '<h4>Log Details</h4>';
    detailsHTML += '<div class="detail-grid">';
    detailsHTML += `<div class="detail-item"><strong>Template:</strong> ${data.parsed_log.template || 'N/A'}</div>`;
    detailsHTML += `<div class="detail-item"><strong>Severity:</strong> <span class="badge ${data.parsed_log.severity.toLowerCase()}">${data.parsed_log.severity}</span></div>`;
    detailsHTML += `<div class="detail-item"><strong>Component:</strong> ${data.parsed_log.component || 'N/A'}</div>`;
    detailsHTML += '</div></div>';
    
    if (data.alert && data.alert.description) {
        detailsHTML += '<div class="report-section">';
        detailsHTML += '<h4>Alert Information</h4>';
        detailsHTML += `<div class="alert-box ${data.alert.severity.toLowerCase()}">${data.alert.description}</div>`;
        detailsHTML += '</div>';
    }
    
    if (data.reasoning_steps && data.reasoning_steps.length > 0) {
        detailsHTML += '<div class="report-section">';
        detailsHTML += '<h4>Reasoning Chain</h4>';
        detailsHTML += '<ol class="reasoning-list">';
        data.reasoning_steps.forEach(step => {
            detailsHTML += `<li>${step}</li>`;
        });
        detailsHTML += '</ol></div>';
    }
    
    reportDetails.innerHTML = detailsHTML;
    
    resultsSection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// Display batch results
function displayBatchResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    const reportSummary = document.getElementById('reportSummary');
    const reportDetails = document.getElementById('reportDetails');
    const anomalyList = document.getElementById('anomalyList');
    const inlineChatSection = document.getElementById('inlineChatSection');
    
    analysisResults = data;
    chatHistory = [];
    
    // Summary
    const anomalyRate = (data.anomalies_detected / data.total_logs * 100).toFixed(2);
    reportSummary.innerHTML = `
        <div class="summary-cards">
            <div class="summary-card">
                <div class="summary-icon blue">
                    <i class="fas fa-file-alt"></i>
                </div>
                <div class="summary-content">
                    <h4>Total Logs</h4>
                    <p>${data.total_logs}</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon red">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="summary-content">
                    <h4>Anomalies Detected</h4>
                    <p>${data.anomalies_detected}</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon yellow">
                    <i class="fas fa-percentage"></i>
                </div>
                <div class="summary-content">
                    <h4>Anomaly Rate</h4>
                    <p>${anomalyRate}%</p>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-icon green">
                    <i class="fas fa-clock"></i>
                </div>
                <div class="summary-content">
                    <h4>Total Time</h4>
                    <p>${data.total_time.toFixed(2)}s</p>
                </div>
            </div>
        </div>
        <div style="margin-top: 1.5rem; text-align: center; display: flex; gap: 1rem; justify-content: center;">
            <button class="btn btn-primary" onclick="viewAnalytics('${data.session_id}')" style="padding: 0.75rem 2rem; font-size: 1rem;">
                <i class="fas fa-chart-line"></i> View Analytics
            </button>
            <button class="btn btn-secondary" onclick="runEvaluation('${data.session_id}')" style="padding: 0.75rem 2rem; font-size: 1rem;">
                <i class="fas fa-flask"></i> Run Evaluation
            </button>
        </div>
    `;
    
    // Details
    reportDetails.innerHTML = `
        <div class="report-section">
            <h4>Analysis Summary</h4>
            <div class="detail-grid">
                <div class="detail-item"><strong>File:</strong> ${uploadedFile.name}</div>
                <div class="detail-item"><strong>System:</strong> ${document.getElementById('batchSystemSelect').selectedOptions[0].text}</div>
                <div class="detail-item"><strong>Avg Time/Log:</strong> ${(data.total_time / data.total_logs).toFixed(3)}s</div>
                <div class="detail-item"><strong>Throughput:</strong> ${(data.total_logs / data.total_time).toFixed(2)} logs/s</div>
            </div>
        </div>
    `;
    
    // Anomaly list
    if (data.anomalies && data.anomalies.length > 0) {
        let anomalyHTML = '<div class="report-section"><h4>Detected Anomalies</h4>';
        data.anomalies.forEach((anomaly, index) => {
            anomalyHTML += `
                <div class="anomaly-item">
                    <div class="anomaly-header">
                        <span class="anomaly-number">#${index + 1}</span>
                        <span class="badge ${anomaly.alert.severity.toLowerCase()}">${anomaly.alert.severity}</span>
                        <span class="anomaly-confidence">Confidence: ${(anomaly.confidence * 100).toFixed(2)}%</span>
                    </div>
                    <div class="anomaly-content">
                        <strong>Log:</strong> ${anomaly.log.content || anomaly.log.message}
                    </div>
                    <div class="anomaly-description">
                        ${anomaly.alert.description || anomaly.alert.explanation}
                    </div>
                </div>
            `;
        });
        anomalyHTML += '</div>';
        anomalyList.innerHTML = anomalyHTML;
    }

    resultsSection.style.display = 'block';
    inlineChatSection.style.display = 'block';
    
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = '';
    addChatMessage('system', `Analysis complete! You can now ask questions about the ${data.total_logs} logs analyzed.`);
    
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function buildAnalysisContextForChat() {
    if (!analysisResults) return '';

    const parts = [];
    if (uploadedFile?.name) {
        parts.push(`File: ${uploadedFile.name}`);
    }

    if (typeof analysisResults.total_logs === 'number') {
        parts.push(`Total logs analyzed: ${analysisResults.total_logs}`);
    }
    if (typeof analysisResults.anomalies_detected === 'number') {
        parts.push(`Anomalies detected: ${analysisResults.anomalies_detected}`);
    }

    if (Array.isArray(analysisResults.anomalies) && analysisResults.anomalies.length > 0) {
        const top = analysisResults.anomalies.slice(0, 5).map((a, i) => {
            const msg = (a.log?.content || a.log?.message || '').toString();
            const sev = (a.alert?.severity || '').toString();
            const desc = (a.alert?.description || a.alert?.explanation || '').toString();
            return `#${i + 1} [${sev}] ${msg}\n${desc}`;
        });
        parts.push(`Top anomalies (up to 5):\n${top.join('\n\n')}`);
    }

    return parts.join('\n');
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    addChatMessage('user', message);
    input.value = '';
    
    const context = buildAnalysisContextForChat();
    
    try {
        addChatMessage('system', 'Thinking...');
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                context: context,
                session_id: currentSessionId,
                history: chatHistory
            })
        });
        
        const data = await response.json();
        
        const chatMessages = document.getElementById('chatMessages');
        const thinkingMsg = chatMessages.lastElementChild;
        if (thinkingMsg && thinkingMsg.textContent.includes('Thinking')) {
            thinkingMsg.remove();
        }
        
        if (data.response) {
            addChatMessage('assistant', data.response);
            chatHistory.push({ role: 'user', content: message });
            chatHistory.push({ role: 'assistant', content: data.response });
        } else {
            addChatMessage('system', 'Error: Unable to get response');
        }
    } catch (error) {
        const chatMessages = document.getElementById('chatMessages');
        const thinkingMsg = chatMessages.lastElementChild;
        if (thinkingMsg) thinkingMsg.remove();
        addChatMessage('system', 'Error: ' + error.message);
    }
}

function addChatMessage(role, content) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'chat-message-avatar';
    avatarDiv.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : 
                         role === 'assistant' ? '<i class="fas fa-robot"></i>' :
                         '<i class="fas fa-info-circle"></i>';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'chat-message-content';
    contentDiv.textContent = content;
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Progress functions
function showProgress(message) {
    const progressSection = document.getElementById('progressSection');
    const progressText = document.getElementById('progressText');
    const progressFill = document.getElementById('progressFill');
    
    progressText.textContent = message;
    progressFill.style.width = '0%';
    progressSection.style.display = 'block';
    progressSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function updateProgress(percentage, message) {
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    progressFill.style.width = Math.min(100, Math.max(0, percentage)) + '%';
    if (message) {
        progressText.textContent = message;
    }
}

function hideProgress() {
    const progressSection = document.getElementById('progressSection');
    setTimeout(() => {
        progressSection.style.display = 'none';
    }, 500);
}

// Sessions Management
async function openSessionsModal() {
    const modal = document.getElementById('sessionsModal');
    modal.style.display = 'flex';
    await loadSessions();
}

function closeSessionsModal() {
    const modal = document.getElementById('sessionsModal');
    modal.style.display = 'none';
}

async function loadSessions() {
    try {
        const response = await fetch('/api/analysis-sessions');
        const data = await response.json();
        
        const sessionsList = document.getElementById('sessionsList');
        
        if (data.success && data.sessions.length > 0) {
            sessionsList.innerHTML = data.sessions.map(session => `
                <div class="session-item" onclick="loadSession('${session.session_id}')">
                    <div class="session-item-header">
                        <div class="session-item-title">
                            <i class="fas fa-file-alt"></i>
                            ${session.filename}
                        </div>
                        <div class="session-item-time">
                            ${new Date(session.timestamp).toLocaleString()}
                        </div>
                    </div>
                    <div class="session-item-details">
                        <div class="session-item-detail">
                            <i class="fas fa-list"></i>
                            ${session.total_logs} logs
                        </div>
                        <div class="session-item-detail">
                            <i class="fas fa-exclamation-triangle"></i>
                            ${session.anomalies_detected} anomalies
                        </div>
                        <div class="session-item-detail">
                            <i class="fas fa-cog"></i>
                            ${session.system_type}
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            sessionsList.innerHTML = `
                <div class="empty-sessions">
                    <i class="fas fa-inbox"></i>
                    <p>No analysis sessions found</p>
                </div>
            `;
        }
    } catch (error) {
        showToast('Error loading sessions: ' + error.message, 'error');
    }
}

async function loadSession(sessionId) {
    try {
        const response = await fetch(`/api/analysis-sessions/${sessionId}`);
        const data = await response.json();
        
        if (data.success) {
            currentSessionId = sessionId;
            analysisResults = data.session;
            displayBatchResults(data.session);
            closeSessionsModal();
            showToast('Session loaded successfully', 'success');
        }
    } catch (error) {
        showToast('Error loading session: ' + error.message, 'error');
    }
}

async function loadExistingSession(sessionId, filename) {
    try {
        showToast(`Loading session: ${filename || 'Previous analysis'}`, 'info');
        
        const response = await fetch(`/api/analysis-sessions/${sessionId}`);
        const data = await response.json();
        
        if (data.success) {
            currentSessionId = sessionId;
            analysisResults = data.session;
            chatHistory = data.session.chat_history || [];
            
            // Display the analysis results
            displayBatchResults(data.session);
            
            // Load chat history into the chat interface
            if (chatHistory.length > 0) {
                const chatMessages = document.getElementById('chatMessages');
                if (chatMessages) {
                    chatMessages.innerHTML = '';
                    chatHistory.forEach(msg => {
                        appendMessage(msg.role, msg.content);
                    });
                }
                
                // Show chat section
                const inlineChatSection = document.getElementById('inlineChatSection');
                if (inlineChatSection) {
                    inlineChatSection.style.display = 'block';
                }
            }
            
            showToast('Session loaded! You can continue chatting.', 'success');
            
            // Scroll to chat section
            setTimeout(() => {
                const inlineChatSection = document.getElementById('inlineChatSection');
                if (inlineChatSection) {
                    inlineChatSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 500);
        }
    } catch (error) {
        console.error('Error loading session:', error);
        showToast('Failed to load session', 'error');
    }
}

// ============================================
// API Log Streaming Functions
// ============================================

let selectedApiSource = null;
let streamingInterval = null;
let streamingStartTime = null;
let streamingDurationInterval = null;
let collectedApiLogs = [];
let isStreamingPaused = false;

// Load configured API sources
async function loadConfiguredAPISources() {
    const loadingEl = document.getElementById('apiSourcesLoading');
    const noSourcesEl = document.getElementById('noApiSources');
    const gridEl = document.getElementById('apiSourcesGrid');
    
    try {
        // Fetch both API connections and network capture status
        const [connectionsResponse, captureResponse] = await Promise.all([
            fetch('/api/api-connections'),
            fetch('/api/network-capture/status')
        ]);
        
        const data = await connectionsResponse.json();
        const captureStatus = await captureResponse.json();
        
        loadingEl.style.display = 'none';
        
        const enabledConnections = (data.connections || []).filter(conn => conn.enabled);
        const sources = [];
        
        // Add network capture source if running
        if (captureStatus.running) {
            const stats = captureStatus.stats || {};
            sources.push({
                id: 'network-capture',
                type: 'network',
                name: 'Network Packet Capture',
                endpoint: `Capturing on ${stats.interface || 'unknown'}`,
                status: 'Active',
                meta: `${stats.packets_captured || 0} packets captured`
            });
        }
        
        // Add API connections
        enabledConnections.forEach(conn => {
            sources.push({
                id: conn.connection_id,
                type: conn.connection_type || 'system',
                name: conn.name,
                endpoint: conn.endpoint,
                status: 'Active',
                meta: conn.auth_type || 'none'
            });
        });
        
        if (sources.length === 0) {
            noSourcesEl.style.display = 'block';
            gridEl.style.display = 'none';
            return;
        }
        
        noSourcesEl.style.display = 'none';
        gridEl.style.display = 'grid';
        
        gridEl.innerHTML = sources.map(source => `
            <div class="api-source-card" onclick="selectApiSource('${source.id}')">
                <span class="source-type-badge source-type-${source.type}">${source.type}</span>
                <div class="source-card-title">${source.name}</div>
                <div class="source-card-endpoint">${source.endpoint}</div>
                <div class="source-card-meta">
                    <div class="source-status">
                        <span class="status-dot"></span>
                        <span>${source.status}</span>
                    </div>
                    <span>${source.meta}</span>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading API sources:', error);
        loadingEl.style.display = 'none';
        noSourcesEl.style.display = 'block';
        gridEl.style.display = 'none';
    }
}

// Select API source
async function selectApiSource(connectionId) {
    try {
        // Check if it's network capture
        if (connectionId === 'network-capture') {
            selectedApiSource = {
                connection_id: 'network-capture',
                name: 'Network Packet Capture',
                connection_type: 'network',
                endpoint: '/api/network-capture/logs',
                auth_type: 'none'
            };
        } else {
            const response = await fetch('/api/api-connections');
            
            if (!response.ok) {
                console.error('Failed to fetch API connections');
                return;
            }
            
            const data = await response.json();
            
            if (!data.connections || data.connections.length === 0) {
                console.log('No API connections available');
                return;
            }
            
            selectedApiSource = data.connections.find(conn => conn.connection_id === connectionId);
            
            if (!selectedApiSource) {
                console.error('API source not found:', connectionId);
                return;
            }
        }
        
        // Update UI
        document.querySelectorAll('.api-source-card').forEach(card => {
            card.classList.remove('selected');
        });
        event.target.closest('.api-source-card').classList.add('selected');
        
        // Show controls
        const controlsEl = document.getElementById('selectedSourceControls');
        if (controlsEl) {
            controlsEl.style.display = 'block';
            document.getElementById('selectedSourceName').textContent = selectedApiSource.name;
        }
        
        showToast(`Selected: ${selectedApiSource.name}`, 'success');
        
    } catch (error) {
        console.error('Error selecting API source:', error);
        showToast('Failed to select API source', 'error');
    }
}

// Fetch and analyze logs from API source
async function fetchAndAnalyzeApiLogs() {
    if (!selectedApiSource) {
        showToast('Please select an API source first', 'warning');
        return;
    }

    const logCount = parseInt(document.getElementById('apiLogCount').value) || 100;
    const analysisMethod = document.getElementById('apiAnalysisMethod').value || 'agentic';
    
    try {
        showToast('Fetching logs from API source...', 'info');
        
        let logs = [];
        
        // Fetch logs based on source type
        if (selectedApiSource.connection_id === 'network-capture') {
            const response = await fetch('/api/network-capture/logs');
            const data = await response.json();
            
            if (!response.ok) {
                showToast(data.error || 'Failed to fetch network capture logs', 'error');
                return;
            }
            
            logs = data.logs || [];
        } else {
            // Fetch from regular API connection
            const response = await fetch(`/api/api-connections/${selectedApiSource.connection_id}/logs?limit=${logCount}`);
            const data = await response.json();
            
            if (!response.ok) {
                showToast(data.error || 'Failed to fetch logs from API', 'error');
                return;
            }
            
            logs = data.logs || [];
        }
        
        if (logs.length === 0) {
            showToast('No logs found from this source. Please ensure network capture is running and capturing packets.', 'error');
            return;
        }
        
        showToast(`Fetched ${logs.length} logs. Preparing analysis...`, 'success');
        
        // Create a temporary file-like object for analysis
        const logContent = logs.map(log => log.content || JSON.stringify(log)).join('\n');
        const blob = new Blob([logContent], { type: 'text/plain' });
        const file = new File([blob], `${selectedApiSource.name}_logs.txt`, { type: 'text/plain' });
        
        // Set as uploaded file
        uploadedFile = file;
        
        // Update file info display in Upload section
        const fileNameEl = document.getElementById('fileName');
        const fileSizeEl = document.getElementById('fileSize');
        const fileInfoEl = document.getElementById('fileInfo');
        const uploadZoneEl = document.getElementById('uploadZone');
        
        if (fileNameEl) fileNameEl.textContent = file.name;
        if (fileSizeEl) fileSizeEl.textContent = formatFileSize(file.size);
        if (fileInfoEl) fileInfoEl.style.display = 'flex';
        if (uploadZoneEl) uploadZoneEl.style.display = 'none';
        
        // Set the analysis method dropdown in Configuration section
        const batchSystemSelect = document.getElementById('batchSystemSelect');
        if (batchSystemSelect) {
            batchSystemSelect.value = analysisMethod;
        }
        
        // Scroll to configuration section
        const configSection = document.querySelector('.section');
        if (configSection) {
            configSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        
        // Auto-start analysis after a short delay
        setTimeout(() => {
            analyzeFile();
        }, 800);
        
    } catch (error) {
        console.error('Error fetching API logs:', error);
        showToast(error.message || 'Failed to fetch logs from API source', 'error');
    }
}

// Navigate to analysis history page with session ID
function viewAnalytics(sessionId) {
    if (sessionId) {
        window.open(`/analysis-history?session_id=${sessionId}`, '_blank');
    } else {
        window.location.href = '/analysis-history';
    }
}

function runEvaluation(sessionId) {
    window.location.href = `/evaluation?session_id=${sessionId}`;
}

// Format date for datetime-local input
function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// Close API streaming
function closeApiStreaming() {
    stopApiStreaming();
    document.getElementById('apiStreamingControls').style.display = 'none';
    selectedApiSource = null;
    
    document.querySelectorAll('.api-source-card').forEach(card => {
        card.classList.remove('selected');
    });
}

// Reset streaming state
function resetStreamingState() {
    collectedApiLogs = [];
    isStreamingPaused = false;
    document.getElementById('logsCollectedCount').textContent = '0';
    document.getElementById('streamingDuration').textContent = '00:00';
    document.getElementById('streamingStatus').textContent = 'Idle';
    document.getElementById('apiLogPreview').innerHTML = `
        <div class="empty-preview">
            <i class="fas fa-inbox"></i>
            <p>No logs collected yet. Start streaming to see logs appear here.</p>
        </div>
    `;
}

// Start API streaming
async function startApiStreaming() {
    if (!selectedApiSource) {
        showToast('Please select an API source first', 'warning');
        return;
    }
    
    const startTime = document.getElementById('apiStartTime').value;
    const endTime = document.getElementById('apiEndTime').value;
    const interval = parseInt(document.getElementById('apiFetchInterval').value) || 5;
    
    if (!startTime || !endTime) {
        showToast('Please select start and end time', 'warning');
        return;
    }
    
    // Update UI
    document.getElementById('streamPlayBtn').style.display = 'none';
    document.getElementById('streamPauseBtn').style.display = 'inline-block';
    document.getElementById('streamStopBtn').style.display = 'inline-block';
    document.getElementById('analyzeApiLogsBtn').style.display = 'none';
    document.getElementById('streamingStatus').textContent = 'Streaming';
    
    streamingStartTime = Date.now();
    isStreamingPaused = false;
    
    // Start duration counter
    streamingDurationInterval = setInterval(updateStreamingDuration, 1000);
    
    // Start fetching logs
    fetchLogsFromAPI();
    streamingInterval = setInterval(fetchLogsFromAPI, interval * 1000);
    
    showToast('Log streaming started', 'success');
}

// Pause API streaming
function pauseApiStreaming() {
    if (streamingInterval) {
        clearInterval(streamingInterval);
        streamingInterval = null;
    }
    
    if (streamingDurationInterval) {
        clearInterval(streamingDurationInterval);
        streamingDurationInterval = null;
    }
    
    isStreamingPaused = true;
    
    document.getElementById('streamPauseBtn').style.display = 'none';
    document.getElementById('streamPlayBtn').style.display = 'inline-block';
    document.getElementById('streamingStatus').textContent = 'Paused';
    
    showToast('Streaming paused', 'info');
}

// Stop API streaming
function stopApiStreaming() {
    if (streamingInterval) {
        clearInterval(streamingInterval);
        streamingInterval = null;
    }
    
    if (streamingDurationInterval) {
        clearInterval(streamingDurationInterval);
        streamingDurationInterval = null;
    }
    
    document.getElementById('streamPlayBtn').style.display = 'inline-block';
    document.getElementById('streamPauseBtn').style.display = 'none';
    document.getElementById('streamStopBtn').style.display = 'none';
    document.getElementById('streamingStatus').textContent = 'Stopped';
    
    if (collectedApiLogs.length > 0) {
        document.getElementById('analyzeApiLogsBtn').style.display = 'inline-block';
        showToast(`Streaming stopped. ${collectedApiLogs.length} logs collected`, 'success');
    } else {
        showToast('Streaming stopped', 'info');
    }
}

// Update streaming duration
function updateStreamingDuration() {
    if (!streamingStartTime) return;
    
    const elapsed = Math.floor((Date.now() - streamingStartTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    
    document.getElementById('streamingDuration').textContent = 
        `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

// Fetch logs from API
async function fetchLogsFromAPI() {
    if (!selectedApiSource || isStreamingPaused) return;
    
    try {
        const startTime = document.getElementById('apiStartTime').value;
        const endTime = document.getElementById('apiEndTime').value;
        
        const response = await fetch('/api/fetch-logs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                connection_id: selectedApiSource.connection_id,
                start_time: startTime,
                end_time: endTime
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.logs && data.logs.length > 0) {
            // Add new logs to collection
            const newLogs = data.logs.filter(log => 
                !collectedApiLogs.some(existing => existing.content === log.content)
            );
            
            collectedApiLogs.push(...newLogs);
            
            // Update UI
            document.getElementById('logsCollectedCount').textContent = collectedApiLogs.length;
            
            // Update preview
            updateLogPreview(newLogs);
            
            if (newLogs.length > 0) {
                console.log(`Fetched ${newLogs.length} new logs`);
            }
        }
        
    } catch (error) {
        console.error('Error fetching logs from API:', error);
        showToast('Error fetching logs from API', 'error');
    }
}

// Update log preview
function updateLogPreview(newLogs) {
    const previewEl = document.getElementById('apiLogPreview');
    
    // Remove empty state if exists
    const emptyPreview = previewEl.querySelector('.empty-preview');
    if (emptyPreview) {
        emptyPreview.remove();
    }
    
    // Add new logs to preview (prepend for newest first)
    newLogs.forEach(log => {
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        
        const timestamp = log.timestamp || new Date().toISOString();
        const content = log.content || log.message || JSON.stringify(log);
        
        logEntry.innerHTML = `
            <span class="log-timestamp">${new Date(timestamp).toLocaleString()}</span>
            <span class="log-content">${escapeHtml(content)}</span>
        `;
        
        previewEl.insertBefore(logEntry, previewEl.firstChild);
    });
    
    // Keep only last 100 logs in preview
    while (previewEl.children.length > 100) {
        previewEl.removeChild(previewEl.lastChild);
    }
}

// Clear API logs
function clearApiLogs() {
    collectedApiLogs = [];
    document.getElementById('logsCollectedCount').textContent = '0';
    document.getElementById('apiLogPreview').innerHTML = `
        <div class="empty-preview">
            <i class="fas fa-inbox"></i>
            <p>No logs collected yet. Start streaming to see logs appear here.</p>
        </div>
    `;
    showToast('Logs cleared', 'info');
}

// Analyze API logs
async function analyzeApiLogs() {
    if (collectedApiLogs.length === 0) {
        showToast('No logs to analyze', 'warning');
        return;
    }
    
    // Convert collected logs to text format
    const logsText = collectedApiLogs.map(log => {
        const timestamp = log.timestamp || new Date().toISOString();
        const content = log.content || log.message || JSON.stringify(log);
        return `${timestamp} ${content}`;
    }).join('\n');
    
    // Create a virtual file from the logs
    const blob = new Blob([logsText], { type: 'text/plain' });
    const file = new File([blob], `${selectedApiSource.name}_logs.txt`, { type: 'text/plain' });
    
    // Set as uploaded file and trigger analysis
    uploadedFile = file;
    
    // Show file info
    document.getElementById('uploadArea').style.display = 'none';
    document.getElementById('uploadInfo').style.display = 'block';
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
    
    // Scroll to analysis section
    document.querySelector('.section-header h3').scrollIntoView({ behavior: 'smooth' });
    
    showToast(`Ready to analyze ${collectedApiLogs.length} logs from ${selectedApiSource.name}`, 'success');
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function clearAllSessions() {
    if (!confirm('Are you sure you want to clear all analysis sessions? This cannot be undone.')) {
        return;
    }
    // ... (rest of the code remains the same)
    
    try {
        const response = await fetch('/api/analysis-sessions', {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('All sessions cleared', 'success');
            await loadSessions();
        }
    } catch (error) {
        showToast('Error clearing sessions: ' + error.message, 'error');
    }
}

// Download report
function downloadReport() {
    if (!analysisResults) return;
    
    const report = JSON.stringify(analysisResults, null, 2);
    const blob = new Blob([report], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analysis_report_${Date.now()}.json`;
    a.click();
}

// Export JSON
function exportJSON() {
    downloadReport();
}

// Clear analysis
function clearAnalysis() {
    document.getElementById('resultsSection').style.display = 'none';
    const postAnalysisChat = document.getElementById('postAnalysisChat');
    if (postAnalysisChat) postAnalysisChat.style.display = 'none';
    const postQ = document.getElementById('postAnalysisQuestion');
    if (postQ) postQ.value = '';
    analysisResults = null;
}
