// Log Analyzer JavaScript

let uploadedFile = null;
let analysisResults = null;
let currentSessionId = null;
let chatHistory = [];

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

// Setup file upload
function setupFileUpload() {
    const fileInput = document.getElementById('fileInput');

    if (!fileInput) {
        console.error('File input element not found');
        return;
    }
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
}

// Handle file selection
function handleFile(file) {
    const allowedTypes = ['.log', '.txt', '.json', '.csv'];
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedTypes.includes(fileExt)) {
        showToast('Invalid file type. Please upload .log, .txt, .json, or .csv files.', 'warning');
        return;
    }
    
    uploadedFile = file;
    
    // Show file info
    document.getElementById('uploadArea').style.display = 'none';
    document.getElementById('uploadInfo').style.display = 'block';
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
}

// Remove file
function removeFile() {
    uploadedFile = null;
    document.getElementById('uploadArea').style.display = 'flex';
    document.getElementById('uploadInfo').style.display = 'none';
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
    
    showProgress('Uploading file...');
    
    try {
        const formData = new FormData();
        formData.append('file', uploadedFile);
        formData.append('system_type', systemType);
        formData.append('max_logs', maxLogs);
        
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

async function clearAllSessions() {
    if (!confirm('Are you sure you want to clear all analysis sessions? This cannot be undone.')) {
        return;
    }
    
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
